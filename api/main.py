"""
api/main.py
===========
FastAPI Web API for Udaan Metrics Flight Analytics & Self-Healing Scraper Registry.

Endpoints:
  GET /                         -> API Info & Sitemap
  GET /index/latest             -> Latest Composite Flight Fare Index
  GET /index/history            -> Trailing Daily Index History (filterable by route & days)
  GET /forecast                 -> Prophet Time-Series Forecast (filterable by route)
  GET /quality/flags            -> Quality-flagged & anomalous fare records
  GET /selectors/health         -> Self-Healing Selector Registry Status & Healing Audit Log

All endpoints read directly from parquet & JSON registry files — no live scraping.
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("udaan_api")

# ──────────────────────────────────────────────────────────────────────────────
# Config & File Paths
# ──────────────────────────────────────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_DIR = os.path.join(_PROJECT_ROOT, "udaan_data", "index")
PROCESSED_DIR = os.path.join(_PROJECT_ROOT, "udaan_data", "processed")
SELECTORS_DIR = os.path.join(_PROJECT_ROOT, "selectors")

INDEX_PARQUET = os.path.join(INDEX_DIR, "fare_index_daily.parquet")
FORECAST_PARQUET = os.path.join(INDEX_DIR, "forecast.parquet")
QUALITY_PARQUET = os.path.join(PROCESSED_DIR, "quality_flagged.parquet")
ANOMALIES_PARQUET = os.path.join(PROCESSED_DIR, "anomalies.parquet")
MASTER_PARQUET = os.path.join(PROCESSED_DIR, "fare_quotes_master.parquet")
HEALING_LOG_JSONL = os.path.join(SELECTORS_DIR, "healing_log.jsonl")

# ──────────────────────────────────────────────────────────────────────────────
# FastAPI App Initialization
# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Udaan Metrics Flight Fare Index & Self-Healing API",
    description="High-frequency Indian aviation market index, data quality engine, and autonomous self-healing scraper monitoring API.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────────────────────────────────────

def _read_parquet_safe(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail=f"Data file '{os.path.basename(path)}' not found. Please run core.run_pipeline first."
        )
    try:
        return pd.read_parquet(path)
    except Exception as e:
        logger.error(f"Error reading parquet '{path}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read parquet data: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api")
def get_root():
    """API Overview & Sitemap."""
    return {
        "service": "Udaan Metrics Flight Analytics API",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": [
            "/index/latest",
            "/index/history?route=DEL-BOM&days=30",
            "/forecast?route=DEL-BOM",
            "/quality/flags?min_confidence=0.8&limit=50",
            "/selectors/health",
        ],
        "status": "operational",
    }


@app.get("/api/index/latest")
def get_latest_index():
    """
    Returns the latest daily composite index, composite fare, data completeness score,
    and route sub-indices.
    """
    df = _read_parquet_safe(INDEX_PARQUET)
    if df.empty:
        raise HTTPException(status_code=404, detail="Fare index file is empty.")

    df = df.sort_values("date")
    latest_row = df.iloc[-1].to_dict()

    # Clean up NaNs for JSON serialization
    clean_row = {k: (None if pd.isna(v) else v) for k, v in latest_row.items()}
    return {
        "status": "success",
        "latest_date": clean_row.get("date"),
        "composite_fare_index": clean_row.get("composite_fare_index"),
        "composite_daily_fare": clean_row.get("composite_daily_fare"),
        "data_completeness": clean_row.get("data_completeness"),
        "total_days_collected": len(df),
        "metrics": clean_row,
    }


@app.get("/api/index/history")
def get_index_history(
    route: Optional[str] = Query(None, description="Filter by route, e.g., DEL-BOM, DEL-BLR"),
    days: int = Query(30, ge=1, le=365, description="Trailing number of days to return"),
):
    """
    Returns trailing daily composite index history. Option to filter by route sub-index.
    """
    df = _read_parquet_safe(INDEX_PARQUET)
    if df.empty:
        return {"status": "success", "count": 0, "records": []}

    df = df.sort_values("date").tail(days)

    records = []
    for _, row in df.iterrows():
        item = {
            "date": row["date"],
            "composite_fare_index": None if pd.isna(row.get("composite_fare_index")) else row.get("composite_fare_index"),
            "composite_daily_fare": None if pd.isna(row.get("composite_daily_fare")) else row.get("composite_daily_fare"),
            "data_completeness": None if pd.isna(row.get("data_completeness")) else row.get("data_completeness"),
        }

        if route:
            r_clean = route.strip().upper()
            sub_idx = row.get(f"index_{r_clean}")
            sub_fare = row.get(f"fare_{r_clean}")
            item["route"] = r_clean
            item[f"index_{r_clean}"] = None if pd.isna(sub_idx) else sub_idx
            item[f"fare_{r_clean}"] = None if pd.isna(sub_fare) else sub_fare
        else:
            # Include all sub-indices
            for col in df.columns:
                if col.startswith("index_") or col.startswith("fare_"):
                    item[col] = None if pd.isna(row[col]) else row[col]

        records.append(item)

    return {
        "status": "success",
        "route_filter": route,
        "days": days,
        "count": len(records),
        "records": records,
    }


@app.get("/api/forecast")
def get_forecast(
    route: Optional[str] = Query(None, description="Target index to forecast, e.g. composite_fare_index or index_DEL-BOM"),
):
    """
    Returns Prophet forward time-series forecasts with 80% confidence intervals.
    """
    if not os.path.exists(FORECAST_PARQUET):
        return {
            "status": "insufficient_history",
            "message": "Forecast dataset not found. Run core.run_pipeline to generate.",
            "records": [],
        }

    df = pd.read_parquet(FORECAST_PARQUET)

    if df.empty:
        return {
            "status": "insufficient_history",
            "message": "Fewer than 14 days of historical index data exist. Prophet forecast skipped to avoid overfitting.",
            "records": [],
        }

    if route:
        target_name = route if route.startswith("index_") or route == "composite_fare_index" else f"index_{route.upper()}"
        df = df[df["target"] == target_name]

    records = df.to_dict(orient="records")
    for r in records:
        for k, v in r.items():
            if pd.isna(v):
                r[k] = None

    return {
        "status": "success",
        "count": len(records),
        "target_filter": route,
        "records": records,
    }


@app.get("/api/quality/flags")
def get_quality_flags(
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence score threshold"),
    flag: Optional[str] = Query(None, description="Filter by quality flag, e.g. price_anomaly_ml, llm_sourced"),
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
):
    """
    Returns data quality flagged records, confidence scores, and anomaly classifications.
    """
    df = _read_parquet_safe(QUALITY_PARQUET)

    # Convert quality_flags column to list if string
    df["quality_flags"] = df["quality_flags"].apply(
        lambda x: list(x) if isinstance(x, (list, pd.Series, set)) else []
    )

    # Filter to only flagged rows by default unless min_confidence is specified
    if flag:
        df = df[df["quality_flags"].apply(lambda flags: flag in flags)]
    else:
        df = df[df["quality_flags"].apply(lambda flags: len(flags) > 0)]

    if min_confidence is not None:
        df = df[df["confidence_score"] >= min_confidence]

    df = df.head(limit)

    records = []
    for _, row in df.iterrows():
        r = row.to_dict()
        clean_r = {k: (None if pd.isna(v) else v) for k, v in r.items()}
        records.append(clean_r)

    return {
        "status": "success",
        "count": len(records),
        "min_confidence_filter": min_confidence,
        "flag_filter": flag,
        "records": records,
    }


@app.get("/api/selectors/health")
def get_selectors_health():
    """
    Returns self-healing status of all scraper site CSS selectors and healing audit log.
    THIS IS THE PRIMARY DEMO ENDPOINT FOR JUDGES TO INSPECT SELF-HEALING REGISTRY STATE.
    """
    sites_summary: Dict[str, Any] = {}

    if os.path.exists(SELECTORS_DIR):
        for fname in os.listdir(SELECTORS_DIR):
            if fname.endswith(".json") and fname != "healing_log.json":
                site_name = fname[:-5]
                fpath = os.path.join(SELECTORS_DIR, fname)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        data = json.load(f)

                    selectors = data.get("selectors", {})
                    pending = data.get("pending_review", {})

                    site_info = {
                        "site": site_name,
                        "active_selectors_count": len(selectors),
                        "pending_review_count": len(pending),
                        "selectors": selectors,
                        "pending_review": pending,
                    }
                    sites_summary[site_name] = site_info
                except Exception as e:
                    logger.error(f"Error reading selector file '{fname}': {e}")

    # Read healing log JSONL
    healing_events: List[dict] = []
    if os.path.exists(HEALING_LOG_JSONL):
        try:
            with open(HEALING_LOG_JSONL, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        healing_events.append(json.loads(line))
        except Exception as e:
            logger.error(f"Error reading healing log jsonl: {e}")

    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "total_monitored_sites": len(sites_summary),
        "total_healing_events_logged": len(healing_events),
        "sites": sites_summary,
        "recent_healing_events": healing_events[-50:],  # return trailing 50 events
    }




@app.get("/api/fares/raw")
def get_raw_fares():
    """
    Fallback endpoint to serve raw fare data from the master parquet file,
    so the legacy React frontend UI components don't break.
    """
    df = _read_parquet_safe(MASTER_PARQUET)
    if df.empty:
        return []
        
    # React app expects a list of dicts.
    # To handle batches that cross midnight, take the last 24 hours of data instead of matching the date string strictly.
    if "scraped_at" in df.columns:
        df["_parsed_dt"] = pd.to_datetime(df["scraped_at"], errors="coerce", utc=True)
        max_dt = df["_parsed_dt"].max()
        if pd.notna(max_dt):
            df = df[df["_parsed_dt"] >= (max_dt - pd.Timedelta(hours=24))]
        df = df.sort_values(by="scraped_at", ascending=False).drop(columns=["_parsed_dt"], errors="ignore")
        
    # Convert bools and NaNs to something JSON serializable
    df = df.fillna("")
    # Convert 'outlier_flag' if it exists to boolean string or native boolean to match frontend expectations
    
    return df.to_dict(orient="records")

@app.get("/api/index/heatmap")
def get_heatmap():
    """
    Returns route-wise percentage change compared to the previous day.
    Uses the pre-aggregated INDEX_PARQUET to quickly calculate differences,
    simulating the old /api/index/heatmap logic.
    """
    df = _read_parquet_safe(INDEX_PARQUET)
    if df.empty:
        return []
        
    df = df.sort_values("date")
    dates = df["date"].unique()
    if len(dates) == 0:
        return []
        
    latest_date = dates[-1]
    prev_date = dates[-2] if len(dates) > 1 else None
    
    latest_row = df[df["date"] == latest_date].iloc[0]
    prev_row = df[df["date"] == prev_date].iloc[0] if prev_date else None
    
    results = []
    # Identify route columns like 'fare_DEL-BOM'
    route_fare_cols = [c for c in df.columns if c.startswith("fare_")]
    for col in route_fare_cols:
        route = col.replace("fare_", "")
        current_fare = latest_row.get(col, 0)
        
        if prev_row is not None:
            prev_fare = prev_row.get(col, current_fare)
        else:
            prev_fare = current_fare
            
        if pd.isna(current_fare): current_fare = 0
        if pd.isna(prev_fare): prev_fare = current_fare
            
        if prev_fare == 0:
            pct_change = 0
        else:
            pct_change = ((current_fare - prev_fare) / prev_fare) * 100
            
        results.append({
            "route": route,
            "pct_change": float(round(pct_change, 2)),
            "current_fare": float(current_fare)
        })
        
    return results


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
