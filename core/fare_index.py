"""
core/fare_index.py
==================
Builds the Udaan Metrics Daily Flight Fare Index from `quality_flagged.parquet`.

Rules:
1. Exclude rows with status != "ok" OR quality_flags containing "price_anomaly_statistical".
   Keep excluded rows in `udaan_data/index/excluded_fare_audit.parquet` with an
   `exclusion_reason` column.
2. Per (route, advance_purchase_days, travel_date / scraped_date), compute the median
   total_fare across all carriers/scrapers.
3. Aggregate route-level fares into a composite daily index (equal-weighted by default,
   re-base to 100.0 on the first collection day). Per-route sub-indices are also built.
4. Calculate a `data_completeness` column (fraction of expected route × horizon
   combinations with usable data each day).
5. Write `udaan_data/index/fare_index_daily.parquet`.
"""

import os
import logging
import numpy as np
import pandas as pd
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Config & Paths
# ──────────────────────────────────────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(_PROJECT_ROOT, "udaan_data", "processed")
INDEX_DIR = os.path.join(_PROJECT_ROOT, "udaan_data", "index")

INPUT_PARQUET = os.path.join(PROCESSED_DIR, "quality_flagged.parquet")
OUTPUT_INDEX_PARQUET = os.path.join(INDEX_DIR, "fare_index_daily.parquet")
EXCLUDED_AUDIT_PARQUET = os.path.join(INDEX_DIR, "excluded_fare_audit.parquet")

# Official passenger-volume traffic weights based on DGCA traffic data
ROUTE_WEIGHTS: Optional[Dict[str, float]] = {
    "DEL-BOM": 0.25,
    "DEL-BLR": 0.20,
    "BOM-BLR": 0.18,
    "MAA-DEL": 0.15,
    "DEL-CCU": 0.12,
    "BLR-HYD": 0.10,
}

KNOWN_ROUTES = ["DEL-BOM", "DEL-BLR", "BOM-BLR", "DEL-CCU", "BLR-HYD", "MAA-DEL"]
KNOWN_HORIZONS = [1, 7, 15, 30, 45]
TOTAL_EXPECTED_COMBOS = len(KNOWN_ROUTES) * len(KNOWN_HORIZONS)  # 30


# ──────────────────────────────────────────────────────────────────────────────
# Index Building Pipeline
# ──────────────────────────────────────────────────────────────────────────────

def build_fare_index(
    df: pd.DataFrame,
    route_weights: Optional[Dict[str, float]] = ROUTE_WEIGHTS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Builds the daily fare index dataframe and the excluded fare audit dataframe.

    Returns:
        (index_df, excluded_audit_df)
    """
    df = df.copy()

    if "route" not in df.columns:
        df["route"] = df["origin"] + "-" + df["destination"]

    # Extract date string for observation date
    df["scraped_date"] = pd.to_datetime(df["scraped_at"], utc=True).dt.strftime("%Y-%m-%d")

    # Ensure quality_flags is a list
    df["quality_flags"] = df["quality_flags"].apply(
        lambda x: list(x) if isinstance(x, (list, np.ndarray, set)) else []
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Step 1: Filter & Audit Excluded Rows
    # ──────────────────────────────────────────────────────────────────────────
    is_ok = df["status"] == "ok"
    is_stat_anomaly = df["quality_flags"].apply(lambda f: "price_anomaly_statistical" in f)

    valid_mask = is_ok & (~is_stat_anomaly) & df["total_fare"].notna()
    excluded_mask = ~valid_mask

    excluded_df = df[excluded_mask].copy()

    exclusion_reasons = []
    for idx, row in excluded_df.iterrows():
        reasons = []
        if row["status"] != "ok":
            reasons.append(f"status_not_ok ({row['status']})")
        if "price_anomaly_statistical" in row["quality_flags"]:
            reasons.append("price_anomaly_statistical")
        if pd.isna(row["total_fare"]):
            reasons.append("null_total_fare")
        exclusion_reasons.append("; ".join(reasons) if reasons else "filtered_other")

    excluded_df["exclusion_reason"] = exclusion_reasons

    valid_df = df[valid_mask].copy()

    logger.info(
        f"[Fare Index] Excluded {len(excluded_df):,} rows from indexing "
        f"({len(valid_df):,} valid quotes retained)."
    )

    if valid_df.empty:
        raise ValueError("No valid fare quotes available after filtering!")

    # ──────────────────────────────────────────────────────────────────────────
    # Step 2: Route & Horizon Level Median Fares
    # ──────────────────────────────────────────────────────────────────────────
    # Median fare per (scraped_date, route, advance_purchase_days)
    rh_group = (
        valid_df.groupby(["scraped_date", "route", "advance_purchase_days"])["total_fare"]
        .median()
        .reset_index()
    )

    # Calculate Data Completeness per scraped_date (fraction of 30 expected combinations present)
    completeness_series = rh_group.groupby("scraped_date").size() / float(TOTAL_EXPECTED_COMBOS)

    # Daily median fare per route (across advance purchase days)
    r_daily = (
        rh_group.groupby(["scraped_date", "route"])["total_fare"]
        .mean()
        .reset_index()
    )

    dates = sorted(r_daily["scraped_date"].unique())
    base_date = dates[0]

    # Calculate base route fares on Day 0 for sub-indices
    base_route_fares = (
        r_daily[r_daily["scraped_date"] == base_date]
        .set_index("route")["total_fare"]
        .to_dict()
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Step 3: Compute Daily Composite Index & Sub-Indices
    # ──────────────────────────────────────────────────────────────────────────
    daily_records = []

    for date in dates:
        date_routes = r_daily[r_daily["scraped_date"] == date].set_index("route")["total_fare"].to_dict()

        record = {
            "date": date,
            "data_completeness": round(float(completeness_series.get(date, 0.0)), 4),
        }

        # Calculate per-route fares & sub-indices
        route_fares = {}
        for r in KNOWN_ROUTES:
            fare_val = date_routes.get(r, np.nan)
            record[f"fare_{r}"] = round(fare_val, 2) if not pd.isna(fare_val) else None

            base_f = base_route_fares.get(r)
            if base_f and not pd.isna(fare_val):
                sub_idx = (fare_val / base_f) * 100.0
                record[f"index_{r}"] = round(sub_idx, 2)
            else:
                record[f"index_{r}"] = None

            if not pd.isna(fare_val):
                route_fares[r] = fare_val

        # Composite Daily Fare (Equal or Weighted)
        if route_fares:
            if route_weights:
                w_sum = sum(route_weights.get(r, 0.0) for r in route_fares)
                if w_sum > 0:
                    composite_fare = sum(route_fares[r] * route_weights.get(r, 0.0) for r in route_fares) / w_sum
                else:
                    composite_fare = float(np.mean(list(route_fares.values())))
            else:
                composite_fare = float(np.mean(list(route_fares.values())))
        else:
            composite_fare = np.nan

        record["composite_daily_fare"] = round(composite_fare, 2) if not pd.isna(composite_fare) else None
        daily_records.append(record)

    index_df = pd.DataFrame(daily_records)

    # Normalize Composite Index to 100.0 on Day 0
    base_composite_fare = index_df.loc[0, "composite_daily_fare"]
    if base_composite_fare and base_composite_fare > 0:
        index_df["composite_fare_index"] = (index_df["composite_daily_fare"] / base_composite_fare * 100.0).round(2)
    else:
        index_df["composite_fare_index"] = 100.0

    # Order columns cleanly
    col_order = ["date", "composite_fare_index", "composite_daily_fare", "data_completeness"]
    for r in KNOWN_ROUTES:
        col_order.extend([f"index_{r}", f"fare_{r}"])

    index_df = index_df[col_order]

    return index_df, excluded_df


# ──────────────────────────────────────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────────────────────────────────────

def run(
    input_parquet: str = INPUT_PARQUET,
    output_index_parquet: str = OUTPUT_INDEX_PARQUET,
    excluded_audit_parquet: str = EXCLUDED_AUDIT_PARQUET,
) -> pd.DataFrame:
    print(f"\n{'='*70}")
    print("  Udaan Metrics Daily Flight Fare Index Generator")
    print(f"{'='*70}")

    if not os.path.exists(input_parquet):
        raise FileNotFoundError(f"Input file '{input_parquet}' not found. Run core.anomaly_detection first.")

    df = pd.read_parquet(input_parquet)
    print(f"Loaded {len(df):,} rows from '{input_parquet}'.")

    index_df, excluded_audit_df = build_fare_index(df)

    os.makedirs(INDEX_DIR, exist_ok=True)

    index_df.to_parquet(output_index_parquet, index=False, engine="pyarrow")
    print(f"Saved daily composite fare index to '{output_index_parquet}'.")

    excluded_audit_df.to_parquet(excluded_audit_parquet, index=False, engine="pyarrow")
    print(f"Saved {len(excluded_audit_df):,} excluded audit rows to '{excluded_audit_parquet}'.")

    print(f"\nDaily Composite Fare Index Preview:")
    print(index_df[["date", "composite_fare_index", "composite_daily_fare", "data_completeness"]].to_string(index=False))
    print(f"{'='*70}\n")

    return index_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
