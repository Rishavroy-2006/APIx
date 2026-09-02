"""
core/forecasting.py
===================
Time-series forecasting module for the APIx Daily Flight Fare Index using Prophet.

Features:
- Fits Prophet models with weekly seasonality enabled (weekend/Monday fare premiums)
  and yearly seasonality disabled (insufficient multi-year history).
- Forecasts 3–7 days ahead with native 80% confidence intervals.
- Combines Prophet interval width with index data_completeness into a single
  unified `forecast_confidence` score (0.0–1.0).
- Guard logic: if fewer than 14 days of historical index data exist, logs a clear,
  prominent warning and skips fitting rather than producing an unreliable forecast.
- Contains a commented-out stub for future LSTM deep learning expansion (`forecast_lstm`).

Output:
- Writes `apix_data/index/forecast.parquet`.
"""

import os
import logging
import numpy as np
import pandas as pd
from typing import Optional, List

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Config & Paths
# ──────────────────────────────────────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_DIR = os.path.join(_PROJECT_ROOT, "apix_data", "index")

INPUT_INDEX_PARQUET = os.path.join(INDEX_DIR, "fare_index_daily.parquet")
OUTPUT_FORECAST_PARQUET = os.path.join(INDEX_DIR, "forecast.parquet")

MIN_HISTORICAL_DAYS = 14
DEFAULT_FORECAST_HORIZON_DAYS = 7


# ──────────────────────────────────────────────────────────────────────────────
# Forecasting Engine
# ──────────────────────────────────────────────────────────────────────────────

def generate_forecasts(
    index_df: pd.DataFrame,
    forecast_horizon_days: int = DEFAULT_FORECAST_HORIZON_DAYS,
    min_historical_days: int = MIN_HISTORICAL_DAYS,
) -> pd.DataFrame:
    """
    Fits Prophet models for composite and per-route sub-indices in `index_df`.

    Returns a DataFrame containing forecasts for all targets:
    [ds, target, yhat, yhat_lower, yhat_upper, forecast_confidence, is_forecast]
    """
    if not PROPHET_AVAILABLE:
        logger.error("[Forecasting] Prophet is not installed. Skipping forecasting.")
        print("\n[WARNING] Prophet library unavailable. Skipping forecast generation.\n")
        return _empty_forecast_df()

    if index_df.empty or "date" not in index_df.columns:
        logger.warning("[Forecasting] Empty or invalid index dataframe supplied.")
        return _empty_forecast_df()

    unique_days = index_df["date"].nunique()

    # ── Guard: Check for minimum required historical points ───────────────────
    if unique_days < min_historical_days:
        warn_msg = (
            f"WARNING: Insufficient historical index data (< {min_historical_days} days: "
            f"found {unique_days} day(s)). Skipping Prophet forecast to avoid unreliable fit."
        )
        logger.warning(f"[Forecasting] {warn_msg}")
        print(f"\n{'!'*70}")
        print(f"  [DEMO/JUDGING NOTICE] {warn_msg}")
        print(f"{'!'*70}\n")
        return _empty_forecast_df()

    index_df = index_df.sort_values("date").copy()
    index_df["ds"] = pd.to_datetime(index_df["date"])

    # Extract target columns to forecast
    target_cols = [c for c in index_df.columns if c == "composite_fare_index" or c.startswith("index_")]

    # Default completeness fallback
    last_completeness = (
        float(index_df["data_completeness"].iloc[-1])
        if "data_completeness" in index_df.columns
        else 1.0
    )

    all_forecasts = []

    for target in target_cols:
        sub_df = index_df[["ds", target, "data_completeness"]].dropna(subset=[target]).copy()
        if len(sub_df) < min_historical_days:
            continue

        df_prophet = pd.DataFrame({
            "ds": sub_df["ds"],
            "y": sub_df[target].astype(float),
        })

        try:
            m = Prophet(
                interval_width=0.80,
                weekly_seasonality=True,
                yearly_seasonality=False,
                daily_seasonality=False,
            )
            m.fit(df_prophet)

            future = m.make_future_dataframe(periods=forecast_horizon_days, freq="D")
            forecast = m.predict(future)

            # Combine Prophet interval width with data completeness for confidence
            # Interval width ratio = (yhat_upper - yhat_lower) / yhat
            # High relative uncertainty lowers confidence
            width = (forecast["yhat_upper"] - forecast["yhat_lower"]).abs()
            denom = forecast["yhat"].abs().clip(lower=1.0)
            uncertainty_ratio = width / denom

            prophet_conf = (1.0 - uncertainty_ratio).clip(lower=0.0, upper=1.0)
            final_conf = (prophet_conf * last_completeness).round(4)

            max_hist_ds = sub_df["ds"].max()

            res = pd.DataFrame({
                "ds":                  forecast["ds"].dt.strftime("%Y-%m-%d"),
                "target":              target,
                "yhat":                forecast["yhat"].round(2),
                "yhat_lower":          forecast["yhat_lower"].round(2),
                "yhat_upper":          forecast["yhat_upper"].round(2),
                "forecast_confidence": final_conf,
                "is_forecast":         forecast["ds"] > max_hist_ds,
            })

            all_forecasts.append(res)
            logger.info(f"[Forecasting] Generated forecast for target '{target}'.")

        except Exception as e:
            logger.error(f"[Forecasting] Prophet fit failed for target '{target}': {e}")

    if not all_forecasts:
        return _empty_forecast_df()

    combined_df = pd.concat(all_forecasts, ignore_index=True)
    return combined_df


def _empty_forecast_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "ds",
            "target",
            "yhat",
            "yhat_lower",
            "yhat_upper",
            "forecast_confidence",
            "is_forecast",
        ]
    )


# ──────────────────────────────────────────────────────────────────────────────
# LSTM Stretch Goal Stub (Commented Out)
# ──────────────────────────────────────────────────────────────────────────────
# def forecast_lstm(
#     df: pd.DataFrame,
#     target_col: str,
#     lookback_days: int = 14,
#     forecast_days: int = 7,
# ) -> pd.DataFrame:
#     """
#     STRETCH GOAL: PyTorch / TensorFlow LSTM Neural Network Time-Series Forecasting.
#
#     NOTE ON DATA REQUIREMENTS:
#     Deep learning sequence architectures (LSTM / GRU) require materially more historical
#     training observations (typically >= 90 to 180 continuous daily periods) to reliably
#     learn non-linear temporal dynamics and seasonal patterns without severe overfitting
#     compared to generalized additive models like Facebook Prophet.
#
#     With short time-series datasets (< 30 days), LSTMs will overfit noise and underperform
#     statistical decomposition models.
#
#     This function is reserved as an architectural extension once multi-month historical
#     scrapes have accumulated in production.
#     """
#     raise NotImplementedError(
#         "LSTM forecasting requires >= 90 days of continuous index history. "
#         "Use Prophet via generate_forecasts() for short time-series histories."
#     )


# ──────────────────────────────────────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────────────────────────────────────

def run(
    input_parquet: str = INPUT_INDEX_PARQUET,
    output_parquet: str = OUTPUT_FORECAST_PARQUET,
    forecast_horizon_days: int = DEFAULT_FORECAST_HORIZON_DAYS,
) -> pd.DataFrame:
    print(f"\n{'='*70}")
    print("  APIx Flight Fare Index Forecasting Pipeline (Prophet)")
    print(f"{'='*70}")

    if not os.path.exists(input_parquet):
        warn = f"Input file '{input_parquet}' not found. Run core.fare_index first."
        print(f"\n[NOTICE] {warn}\n")
        df_empty = _empty_forecast_df()
        os.makedirs(INDEX_DIR, exist_ok=True)
        df_empty.to_parquet(output_parquet, index=False, engine="pyarrow")
        return df_empty

    index_df = pd.read_parquet(input_parquet)
    print(f"Loaded {len(index_df):,} daily index records from '{input_parquet}'.")

    forecast_df = generate_forecasts(index_df, forecast_horizon_days=forecast_horizon_days)

    os.makedirs(INDEX_DIR, exist_ok=True)
    forecast_df.to_parquet(output_parquet, index=False, engine="pyarrow")
    print(f"Saved forecast dataset ({len(forecast_df):,} rows) to '{output_parquet}'.")
    print(f"{'='*70}\n")

    return forecast_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
