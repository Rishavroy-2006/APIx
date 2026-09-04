"""
core/quality_scoring.py
=======================
Reads udaan_data/processed/fare_quotes_master.parquet, computes a confidence_score
(0.0–1.0) and quality_flags (list[str]) for every row, and writes the result to
udaan_data/processed/quality_flagged.parquet.

Scoring rules (additive from 1.0; clamped to [0, 1]):
  -0.30  flag "llm_sourced"          if data_source_method == "llm_fallback"
  -0.15  flag "fare_estimated"       if fare_split_estimated == True
  -0.50  flag "missing_price"        if status == "ok" AND total_fare is null
  -0.20  flag "stale_selector"       if the site's selectors/<site>.json has
                                      last_verified_at older than STALE_DAYS days
  +0.10  flag "cross_source_confirmed" if the same flight_num + travel_date has a
         (capped at 1.0)              matching total_fare (within 2%) from a
                                      different source_scraper on the same scraped
                                      date — uses OTA aggregators to cross-check
                                      airline-direct data.
  ---    flag "price_anomaly"        PLACEHOLDER — filled in by Step 8.
"""

import os
import json
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(_PROJECT_ROOT, "udaan_data", "processed")
MASTER_PARQUET = os.path.join(PROCESSED_DIR, "fare_quotes_master.parquet")
OUTPUT_PARQUET = os.path.join(PROCESSED_DIR, "quality_flagged.parquet")
SELECTORS_DIR = os.path.join(_PROJECT_ROOT, "selectors")

STALE_DAYS = 14
CROSS_SOURCE_TOLERANCE = 0.02   # 2% fare tolerance for cross-source confirmation

IST = timezone(timedelta(hours=5, minutes=30))

# Map source_scraper → selector site JSON name
_SCRAPER_TO_SITE = {
    "indigo":      "indigo",
    "air_india":   "air_india",
    "spicejet":    "spicejet",
    "akasa":       "akasa",
    "makemytrip":  "makemytrip",
    "goibibo":     "goibibo",
}


# ──────────────────────────────────────────────────────────────────────────────
# Selector staleness helpers (cached per run so we read each JSON once)
# ──────────────────────────────────────────────────────────────────────────────

def _load_selector_max_verified_at(site: str) -> Optional[datetime]:
    """Return the *oldest* last_verified_at across all active selectors for a site."""
    path = os.path.join(SELECTORS_DIR, f"{site}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        timestamps = []
        for entry in data.get("selectors", {}).values():
            ts_str = entry.get("last_verified_at")
            if ts_str:
                try:
                    dt = datetime.fromisoformat(ts_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=IST)
                    timestamps.append(dt)
                except ValueError:
                    pass
        return min(timestamps) if timestamps else None
    except Exception as e:
        logger.warning(f"[quality_scoring] Could not load selector file for '{site}': {e}")
        return None


def _build_stale_site_set(now: datetime) -> set[str]:
    """Return set of site names whose selectors are older than STALE_DAYS."""
    stale = set()
    for scraper, site in _SCRAPER_TO_SITE.items():
        oldest = _load_selector_max_verified_at(site)
        if oldest is None:
            # No selector file → treat as stale (unknown verification)
            stale.add(scraper)
        else:
            if now.tzinfo is None:
                now = now.replace(tzinfo=IST)
            age = now - oldest
            if age.days > STALE_DAYS:
                stale.add(scraper)
    return stale


# ──────────────────────────────────────────────────────────────────────────────
# Cross-source confirmation
# ──────────────────────────────────────────────────────────────────────────────

def _build_cross_source_keys(df: pd.DataFrame) -> set[tuple]:
    """
    Return a set of (flight_num, travel_date, scraped_date) tuples where the
    same flight appears from ≥2 different source_scrapers with total_fare
    within CROSS_SOURCE_TOLERANCE of each other.

    Algorithm:
      Group ok-status rows by (flight_num, travel_date, scraped_date).
      Within each group that has >1 distinct source_scraper, check whether any
      pair of fares agrees within 2%.  If yes → every row in that group is
      cross_source_confirmed.
    """
    ok = df[
        (df["status"] == "ok") &
        df["total_fare"].notna() &
        df["flight_num"].notna() &
        (df["flight_num"] != "unknown") &
        (df["flight_num"] != "error")
    ].copy()

    if ok.empty:
        return set()

    # scraped_date = calendar date portion of scraped_at (handles tz-aware ISO strings)
    ok["_scraped_date"] = pd.to_datetime(ok["scraped_at"], utc=True).dt.strftime("%Y-%m-%d")

    confirmed_keys: set[tuple] = set()

    group_cols = ["flight_num", "travel_date", "_scraped_date"]
    for key, group in ok.groupby(group_cols):
        if group["source_scraper"].nunique() < 2:
            continue
        fares = group["total_fare"].values
        sources = group["source_scraper"].values
        # Check any cross-source pair
        n = len(fares)
        for i in range(n):
            for j in range(i + 1, n):
                if sources[i] == sources[j]:
                    continue
                f1, f2 = float(fares[i]), float(fares[j])
                if f1 == 0 or f2 == 0:
                    continue
                if abs(f1 - f2) / max(f1, f2) <= CROSS_SOURCE_TOLERANCE:
                    confirmed_keys.add(key)
                    break
            if key in confirmed_keys:
                break

    return confirmed_keys


# ──────────────────────────────────────────────────────────────────────────────
# Main scoring function
# ──────────────────────────────────────────────────────────────────────────────

def compute_quality_scores(
    df: pd.DataFrame,
    now: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Add `confidence_score` (float, 0–1) and `quality_flags` (list[str]) columns
    to `df`.  Input DataFrame must have the fare_quotes_master.parquet schema.
    Returns a new DataFrame (does not modify in place).
    """
    if now is None:
        now = datetime.now(IST)

    df = df.copy()

    # Pre-compute staleness and cross-source confirmation once
    stale_scrapers = _build_stale_site_set(now)
    confirmed_keys = _build_cross_source_keys(df)

    # Add scraped_date column for cross-source lookup
    df["_scraped_date"] = pd.to_datetime(df["scraped_at"], utc=True).dt.strftime("%Y-%m-%d")

    scores = []
    flags_list = []

    missing_price_count = 0

    for _, row in df.iterrows():
        score = 1.0
        flags: list[str] = []

        # ── Rule 1: LLM sourced ──────────────────────────────────────────────
        if row.get("data_source_method") == "llm_fallback":
            score -= 0.30
            flags.append("llm_sourced")

        # ── Rule 2: Fare split estimated ────────────────────────────────────
        estimated = row.get("fare_split_estimated")
        if estimated is True or str(estimated).lower() == "true":
            score -= 0.15
            flags.append("fare_estimated")

        # ── Rule 3: Missing price on ok row (loud surface) ──────────────────
        if row.get("status") == "ok" and pd.isna(row.get("total_fare")):
            score -= 0.50
            flags.append("missing_price")
            missing_price_count += 1

        # ── Rule 4: Stale selector ──────────────────────────────────────────
        if row.get("source_scraper") in stale_scrapers:
            score -= 0.20
            flags.append("stale_selector")

        # ── Rule 5: Cross-source confirmed (+0.10, capped at 1.0) ───────────
        key = (
            row.get("flight_num"),
            row.get("travel_date"),
            row.get("_scraped_date"),
        )
        if key in confirmed_keys:
            score = min(1.0, score + 0.10)
            flags.append("cross_source_confirmed")

        # ── Placeholder for Step 8 ──────────────────────────────────────────
        # "price_anomaly" flag will be appended here by the anomaly detection
        # module.  Do not compute it here.

        # ── Clamp ───────────────────────────────────────────────────────────
        score = max(0.0, min(1.0, score))
        scores.append(round(score, 4))
        flags_list.append(flags)

    if missing_price_count > 0:
        logger.error(
            f"[quality_scoring] ALERT: {missing_price_count} row(s) have status='ok' "
            f"but null total_fare — this should never happen! Investigate immediately."
        )

    df["confidence_score"] = scores
    df["quality_flags"] = flags_list
    df.drop(columns=["_scraped_date"], inplace=True)
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def run(
    input_parquet: str = MASTER_PARQUET,
    output_parquet: str = OUTPUT_PARQUET,
) -> pd.DataFrame:
    print(f"\n{'='*70}")
    print("  Udaan Metrics Quality Scoring")
    print(f"{'='*70}")

    if not os.path.exists(input_parquet):
        raise FileNotFoundError(f"Master parquet not found at '{input_parquet}'. Run core.ingest first.")

    df = pd.read_parquet(input_parquet)
    print(f"Loaded {len(df):,} rows from '{input_parquet}'.")

    now = datetime.now(IST)
    scored = compute_quality_scores(df, now=now)

    # Summary
    flag_counts: dict[str, int] = {}
    for flags in scored["quality_flags"]:
        for f in flags:
            flag_counts[f] = flag_counts.get(f, 0) + 1

    print(f"\nScoring Summary:")
    print(f"  Mean confidence score : {scored['confidence_score'].mean():.4f}")
    print(f"  Min confidence score  : {scored['confidence_score'].min():.4f}")
    print(f"  Score = 1.0 (perfect) : {(scored['confidence_score'] == 1.0).sum():,}")
    print(f"\nFlag counts:")
    for flag, count in sorted(flag_counts.items()):
        print(f"  {flag:<30s}: {count:,}")

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    scored.to_parquet(output_parquet, index=False, engine="pyarrow")
    print(f"\nWrote {len(scored):,} rows to '{output_parquet}'.")
    print(f"{'='*70}\n")
    return scored


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
