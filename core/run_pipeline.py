"""
core/run_pipeline.py
====================
Single master entrypoint for the Udaan Metrics Data & Analytics Pipeline.

Executes stages in sequence:
  1. Data Ingestion      (core.ingest)
  2. Quality Scoring     (core.quality_scoring)
  3. Anomaly Detection   (core.anomaly_detection)
  4. Fare Indexing       (core.fare_index)
  5. Index Forecasting   (core.forecasting) [Optional: --skip-forecast]

Outputs:
  - Clear section headers in terminal console output.
  - JSON run manifest written to `udaan_data/run_manifests/<timestamp>.json` and
    `udaan_data/run_manifests/latest_manifest.json`.
"""

import os
import sys
import json
import time
import argparse
import logging
from datetime import datetime, timezone, timedelta

from core import ingest
from core import quality_scoring
from core import anomaly_detection
from core import fare_index
from core import forecasting

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_DIR = os.path.join(_PROJECT_ROOT, "udaan_data", "run_manifests")


def print_section_header(title: str, step_num: int, total_steps: int = 5) -> None:
    banner = f" STAGE {step_num}/{total_steps}: {title} "
    print(f"\n{'='*75}")
    print(f"{banner:^75}")
    print(f"{'='*75}\n")


def execute_pipeline(skip_forecast: bool = False) -> dict:
    start_time = time.time()
    run_dt = datetime.now(IST)
    timestamp_str = run_dt.strftime("%Y%m%d_%H%M%SIST")

    manifest = {
        "run_id": timestamp_str,
        "started_at": run_dt.isoformat(),
        "skip_forecast": skip_forecast,
        "stages": {},
        "status": "in_progress",
    }

    total_steps = 4 if skip_forecast else 5

    try:
        # ──────────────────────────────────────────────────────────────────────
        # STAGE 1: Data Ingestion
        # ──────────────────────────────────────────────────────────────────────
        print_section_header("Data Ingestion (CSV -> Parquet)", 1, total_steps)
        ingest_start = time.time()
        master_df = ingest.run()
        ingest_duration = time.time() - ingest_start

        manifest["stages"]["ingest"] = {
            "duration_seconds": round(ingest_duration, 2),
            "master_rows": len(master_df),
            "output_file": ingest.PARQUET_PATH,
        }

        # ──────────────────────────────────────────────────────────────────────
        # STAGE 2: Quality Scoring
        # ──────────────────────────────────────────────────────────────────────
        print_section_header("Data Quality & Confidence Scoring", 2, total_steps)
        qs_start = time.time()
        qs_df = quality_scoring.run()
        qs_duration = time.time() - qs_start

        flag_counts = {}
        for flags in qs_df["quality_flags"]:
            for f in flags:
                flag_counts[f] = flag_counts.get(f, 0) + 1

        manifest["stages"]["quality_scoring"] = {
            "duration_seconds": round(qs_duration, 2),
            "evaluated_rows": len(qs_df),
            "mean_confidence_score": round(float(qs_df["confidence_score"].mean()), 4),
            "perfect_score_rows": int((qs_df["confidence_score"] == 1.0).sum()),
            "flag_counts": flag_counts,
            "output_file": quality_scoring.OUTPUT_PARQUET,
        }

        # ──────────────────────────────────────────────────────────────────────
        # STAGE 3: Anomaly Detection
        # ──────────────────────────────────────────────────────────────────────
        print_section_header("Anomaly Detection (MAD + IsolationForest)", 3, total_steps)
        anom_start = time.time()
        anom_df = anomaly_detection.run()
        anom_duration = time.time() - anom_start

        anom_flag_counts = {}
        for flags in anom_df["quality_flags"]:
            for f in flags:
                anom_flag_counts[f] = anom_flag_counts.get(f, 0) + 1

        flagged_count = int((anom_df["quality_flags"].apply(len) > 0).sum())

        manifest["stages"]["anomaly_detection"] = {
            "duration_seconds": round(anom_duration, 2),
            "evaluated_rows": len(anom_df),
            "total_flagged_rows": flagged_count,
            "mean_confidence_score": round(float(anom_df["confidence_score"].mean()), 4),
            "mean_anomaly_score": round(float(anom_df["anomaly_score"].mean()), 4),
            "flag_counts": anom_flag_counts,
            "output_file": anomaly_detection.OUTPUT_PARQUET,
            "anomalies_file": anomaly_detection.ANOMALIES_PARQUET,
        }

        # ──────────────────────────────────────────────────────────────────────
        # STAGE 4: Fare Indexing
        # ──────────────────────────────────────────────────────────────────────
        print_section_header("Daily Fare Index Calculation", 4, total_steps)
        index_start = time.time()
        idx_df = fare_index.run()
        index_duration = time.time() - index_start

        manifest["stages"]["fare_index"] = {
            "duration_seconds": round(index_duration, 2),
            "indexed_dates": int(len(idx_df)),
            "date_range": [str(idx_df["date"].min()), str(idx_df["date"].max())] if not idx_df.empty else [],
            "latest_composite_index": float(idx_df["composite_fare_index"].iloc[-1]) if not idx_df.empty else None,
            "latest_completeness": float(idx_df["data_completeness"].iloc[-1]) if not idx_df.empty else None,
            "output_file": fare_index.OUTPUT_INDEX_PARQUET,
            "audit_file": fare_index.EXCLUDED_AUDIT_PARQUET,
        }

        # ──────────────────────────────────────────────────────────────────────
        # STAGE 5: Forecasting (Optional)
        # ──────────────────────────────────────────────────────────────────────
        if skip_forecast:
            print_section_header("Index Forecasting (SKIPPED via --skip-forecast)", 5, total_steps)
            manifest["stages"]["forecasting"] = {
                "executed": False,
                "reason": "Skipped via --skip-forecast flag",
            }
        else:
            print_section_header("Time-Series Forecasting (Prophet)", 5, total_steps)
            fc_start = time.time()
            fc_df = forecasting.run()
            fc_duration = time.time() - fc_start

            manifest["stages"]["forecasting"] = {
                "executed": True,
                "duration_seconds": round(fc_duration, 2),
                "forecast_rows": len(fc_df),
                "targets_forecasted": list(fc_df["target"].unique()) if not fc_df.empty else [],
                "output_file": forecasting.OUTPUT_FORECAST_PARQUET,
            }

        # ──────────────────────────────────────────────────────────────────────
        # Complete Pipeline Summary & Manifest Output
        # ──────────────────────────────────────────────────────────────────────
        elapsed_total = time.time() - start_time
        manifest["completed_at"] = datetime.now(IST).isoformat()
        manifest["duration_seconds"] = round(elapsed_total, 2)
        manifest["status"] = "success"

        os.makedirs(MANIFEST_DIR, exist_ok=True)
        manifest_path = os.path.join(MANIFEST_DIR, f"{timestamp_str}.json")
        latest_manifest_path = os.path.join(MANIFEST_DIR, "latest_manifest.json")

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        with open(latest_manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*75}")
        print(f"  Udaan Metrics Pipeline Execution Completed Successfully in {elapsed_total:.2f}s")
        print(f"{'='*75}")
        print(f"  Run Manifest Saved To: {manifest_path}")
        print(f"  Latest Manifest Link:  {latest_manifest_path}")
        print(f"{'='*75}\n")

        return manifest

    except Exception as e:
        logger.error(f"[Pipeline] Execution failed with error: {e}", exc_info=True)
        manifest["status"] = "failed"
        manifest["error"] = str(e)

        os.makedirs(MANIFEST_DIR, exist_ok=True)
        manifest_path = os.path.join(MANIFEST_DIR, f"{timestamp_str}_failed.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        raise e


def main():
    parser = argparse.ArgumentParser(
        description="Udaan Metrics Master Data & Analytics Pipeline Runner"
    )
    parser.add_argument(
        "--skip-forecast",
        action="store_true",
        help="Skip Stage 5 (Prophet forecasting) for fast development iteration.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    execute_pipeline(skip_forecast=args.skip_forecast)


if __name__ == "__main__":
    main()
