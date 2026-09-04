"""
core/anomaly_detection.py
========================
Two-pass anomaly detection on flight fare quotes:

Pass 1 (Statistical Baseline):
  Group by (route, carrier_code, advance_purchase_days).
  Compute rolling median and MAD (Median Absolute Deviation) of total_fare.
  Flag quotes where |total_fare - median| > 3.5 * MAD as "price_anomaly_statistical".
  Apply -0.25 penalty to confidence_score (clamped to [0.0, 1.0]).

Pass 2 (ML IsolationForest - optional/stretch):
  Features per route: (advance_purchase_days, day_of_week, total_fare, carrier_code_encoded, group_mean, group_std).
  Fit sklearn IsolationForest per route on historical valid points.
  Skip gracefully if route has < 50 historical points.
  Flag outliers (-1 predictions) as "price_anomaly_ml" and populates `anomaly_score`.

Writes:
  1. udaan_data/processed/quality_flagged.parquet (updated in-place with anomaly flags & scores)
  2. udaan_data/processed/anomalies.parquet (contains only flagged rows for dashboard view)
"""

import os
import logging
import numpy as np
import pandas as pd
from typing import Optional
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(_PROJECT_ROOT, "udaan_data", "processed")
INPUT_PARQUET = os.path.join(PROCESSED_DIR, "quality_flagged.parquet")
OUTPUT_PARQUET = os.path.join(PROCESSED_DIR, "quality_flagged.parquet")
ANOMALIES_PARQUET = os.path.join(PROCESSED_DIR, "anomalies.parquet")

MIN_ML_SAMPLES = 50
MAD_THRESHOLD = 3.5
STAT_PENALTY = 0.25


# ──────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────────────────────────────────────

def _compute_mad(series: pd.Series) -> float:
    """Compute Median Absolute Deviation (MAD) of a numeric series."""
    median = series.median()
    return float((series - median).abs().median())


# ──────────────────────────────────────────────────────────────────────────────
# Main Anomaly Detection
# ──────────────────────────────────────────────────────────────────────────────

def detect_anomalies(
    df: pd.DataFrame,
    min_ml_samples: int = MIN_ML_SAMPLES,
    mad_threshold: float = MAD_THRESHOLD,
) -> pd.DataFrame:
    """
    Applies Pass 1 (Statistical MAD) and Pass 2 (ML IsolationForest) to `df`.
    Returns updated DataFrame with modified `quality_flags`, `confidence_score`,
    and a new `anomaly_score` column.
    """
    df = df.copy()

    if "route" not in df.columns:
        df["route"] = df["origin"] + "-" + df["destination"]

    if "anomaly_score" not in df.columns:
        df["anomaly_score"] = 0.0

    # Ensure quality_flags is a list of strings per row
    df["quality_flags"] = df["quality_flags"].apply(
        lambda x: list(x) if isinstance(x, (list, np.ndarray, set)) else []
    )

    # ──────────────────────────────────────────────────────────────────────────
    # PASS 1: Statistical Baseline (Group MAD)
    # ──────────────────────────────────────────────────────────────────────────
    logger.info("[Anomaly Detection] Running Pass 1: Statistical MAD baseline...")

    valid_mask = (df["status"] == "ok") & df["total_fare"].notna()
    ok_df = df[valid_mask].copy()

    # Group by (route, carrier_code, advance_purchase_days)
    group_cols = ["route", "carrier_code", "advance_purchase_days"]

    stat_anomalies = set()

    for group_key, group in ok_df.groupby(group_cols):
        fares = group["total_fare"]
        if len(fares) < 3:
            continue

        median_fare = fares.median()
        mad_fare = _compute_mad(fares)

        # Avoid division by zero when all fares in group are identical
        effective_mad = max(mad_fare, 10.0)

        for idx, fare in fares.items():
            diff = abs(fare - median_fare)
            if diff > mad_threshold * effective_mad and diff > 100.0:
                stat_anomalies.add(idx)

    # Apply Pass 1 results
    new_confidence = []
    updated_flags = []

    for idx, row in df.iterrows():
        flags = list(row["quality_flags"])
        score = float(row.get("confidence_score", 1.0))

        if idx in stat_anomalies:
            if "price_anomaly_statistical" not in flags:
                flags.append("price_anomaly_statistical")
            score = max(0.0, score - STAT_PENALTY)

        new_confidence.append(round(score, 4))
        updated_flags.append(flags)

    df["confidence_score"] = new_confidence
    df["quality_flags"] = updated_flags

    logger.info(f"[Anomaly Detection] Pass 1 complete. Flagged {len(stat_anomalies):,} statistical anomalies.")

    # ──────────────────────────────────────────────────────────────────────────
    # PASS 2: ML (IsolationForest per Route)
    # ──────────────────────────────────────────────────────────────────────────
    logger.info("[Anomaly Detection] Running Pass 2: IsolationForest ML models...")

    anomaly_scores = pd.Series(0.0, index=df.index, dtype=float)
    ml_anomalies_count = 0

    # Ensure travel_date is datetime for day-of-week extraction
    df["_travel_dt"] = pd.to_datetime(df["travel_date"], errors="coerce")

    # Pre-calculate group statistics for ML features
    group_stats = df[valid_mask].groupby(group_cols)["total_fare"].agg(["mean", "std"]).reset_index()
    group_stats.rename(columns={"mean": "_grp_mean", "std": "_grp_std"}, inplace=True)
    group_stats["_grp_std"] = group_stats["_grp_std"].fillna(0.0)

    df_ml = df.merge(group_stats, on=group_cols, how="left")
    df_ml["_grp_mean"] = df_ml["_grp_mean"].fillna(df_ml["total_fare"])
    df_ml["_grp_std"] = df_ml["_grp_std"].fillna(0.0)

    for route_name, route_group in df_ml.groupby("route"):
        valid_route_indices = route_group[
            (route_group["status"] == "ok") & route_group["total_fare"].notna()
        ].index

        if len(valid_route_indices) < min_ml_samples:
            logger.warning(
                f"[Anomaly Detection] Skipping ML pass for route '{route_name}' "
                f"(insufficient sample count: {len(valid_route_indices)} < {min_ml_samples})"
            )
            continue

        route_sub = df_ml.loc[valid_route_indices].copy()

        # Build features matrix X
        feature_df = pd.DataFrame({
            "advance_days": route_sub["advance_purchase_days"].astype(float),
            "day_of_week":  route_sub["_travel_dt"].dt.dayofweek.astype(float),
            "total_fare":   route_sub["total_fare"].astype(float),
            "grp_mean":     route_sub["_grp_mean"].astype(float),
            "grp_std":      route_sub["_grp_std"].astype(float),
        })

        # One-hot encode carrier_code
        carrier_dummies = pd.get_dummies(route_sub["carrier_code"], prefix="carrier")
        X = pd.concat([feature_df, carrier_dummies], axis=1).fillna(0.0)

        try:
            iso = IsolationForest(
                n_estimators=100,
                contamination="auto",
                random_state=42,
            )
            iso.fit(X)

            # decision_function: lower means more anomalous.
            # Invert sign so higher positive score = higher anomaly.
            scores = -iso.decision_function(X)
            preds = iso.predict(X) # -1 for anomaly, 1 for inlier

            for i, idx in enumerate(valid_route_indices):
                anomaly_scores.at[idx] = float(scores[i])
                if preds[i] == -1:
                    if "price_anomaly_ml" not in df.at[idx, "quality_flags"]:
                        df.at[idx, "quality_flags"].append("price_anomaly_ml")
                    ml_anomalies_count += 1

        except Exception as e:
            logger.error(f"[Anomaly Detection] Error running IsolationForest for route '{route_name}': {e}")

    df["anomaly_score"] = anomaly_scores.round(4)
    df.drop(columns=["_travel_dt"], inplace=True, errors="ignore")

    logger.info(f"[Anomaly Detection] Pass 2 complete. Flagged {ml_anomalies_count:,} ML anomalies.")
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────────────────────────────────────

def run(
    input_parquet: str = INPUT_PARQUET,
    output_parquet: str = OUTPUT_PARQUET,
    anomalies_parquet: str = ANOMALIES_PARQUET,
) -> pd.DataFrame:
    print(f"\n{'='*70}")
    print("  Udaan Metrics Anomaly Detection Pipeline")
    print(f"{'='*70}")

    if not os.path.exists(input_parquet):
        raise FileNotFoundError(f"Input file '{input_parquet}' not found. Run core.quality_scoring first.")

    df = pd.read_parquet(input_parquet)
    print(f"Loaded {len(df):,} rows from '{input_parquet}'.")

    processed = detect_anomalies(df)

    # Filter rows with quality flags for anomalies parquet
    flagged_df = processed[processed["quality_flags"].apply(lambda f: len(f) > 0)].copy()

    # Summary report
    flag_counts: dict[str, int] = {}
    for flags in processed["quality_flags"]:
        for f in flags:
            flag_counts[f] = flag_counts.get(f, 0) + 1

    print(f"\nPipeline Summary:")
    print(f"  Total Rows Evaluated   : {len(processed):,}")
    print(f"  Total Flagged Rows     : {len(flagged_df):,}")
    print(f"  Mean Confidence Score  : {processed['confidence_score'].mean():.4f}")
    print(f"  Mean Anomaly Score     : {processed['anomaly_score'].mean():.4f}")
    print(f"\nAll Active Quality Flags:")
    for flag, count in sorted(flag_counts.items()):
        print(f"  {flag:<30s}: {count:,}")

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    processed.to_parquet(output_parquet, index=False, engine="pyarrow")
    print(f"\nSaved updated dataset with anomaly scores to '{output_parquet}'.")

    flagged_df.to_parquet(anomalies_parquet, index=False, engine="pyarrow")
    print(f"Saved {len(flagged_df):,} flagged rows to '{anomalies_parquet}'.")
    print(f"{'='*70}\n")

    return processed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
