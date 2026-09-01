import os
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import math

app = FastAPI(title="APIx Backend", description="Serving the Airfare Price Index Data")

# Allow CORS for local React dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def safe_nan(val):
    if pd.isna(val):
        return None
    return val

@app.get("/api/index/daily")
def get_daily_index():
    composite_path = os.path.join("apix_data", "index", "apix_composite_index.csv")
    if not os.path.exists(composite_path):
        return {"error": "No composite index found"}
    
    df = pd.read_csv(composite_path)
    if df.empty:
        return {"error": "Composite index is empty"}
    
    # Sort by date descending and get the latest day's data
    df = df.sort_values(by="date", ascending=False)
    latest_date = df.iloc[0]["date"]
    
    # Get all rows for the latest date (all horizons)
    today_df = df[df["date"] == latest_date]
    
    # Priority 1: Calculate index ratio vs base period
    base_date = df["date"].min()
    base_df = df[df["date"] == base_date]
    base_score = base_df["composite_score"].mean()
    if base_score == 0:
        base_score = 1
        
    current_score = today_df["composite_score"].mean()
    index_value = (current_score / base_score) * 100
    
    return {
        "value": round(index_value, 1),
        "date": latest_date,
        "status": "Live Official Data",
        "carriers": ["IndiGo", "SpiceJet", "Air India", "Akasa Air"],
        "routes_tracked": 6,
        "days_live": len(df["date"].unique()),
        "advance_windows": len(today_df),
        "timestamp": f"{latest_date}T23:59:00+05:30"
    }

@app.get("/api/index/route/{pair}")
def get_route_index(pair: str):
    # pair format expected: DEL-BOM
    daily_path = os.path.join("apix_data", "index", "apix_index_daily.csv")
    if not os.path.exists(daily_path):
        return {"trend": []}
    
    try:
        origin, dest = pair.split("-")
    except ValueError:
        return {"trend": []}
        
    df = pd.read_csv(daily_path)
    
    # Filter by route and just look at T+1 for the trend, or average all? 
    # Let's average across all horizons for simplicity to form a single trendline.
    route_df = df[(df["origin"] == origin) & (df["destination"] == dest)]
    if route_df.empty:
        return {"trend": []}
        
    # Priority 4: Group by collection date (`scraped_at`) not travel date
    if "scraped_at" in route_df.columns:
        route_df["date"] = route_df["scraped_at"].str[:10]
    else:
        route_df["date"] = route_df["travel_date"]
        
    date_col = "date"
        
    trend_df = route_df.groupby(date_col)["total_fare"].median().reset_index()
    trend_df = trend_df.sort_values(date_col)
    
    # We want a base 100 index normalized from day 1 for the chart
    base_price = trend_df.iloc[0]["total_fare"]
    if base_price == 0:
        base_price = 1 # avoid div by zero
        
    trend = []
    for _, row in trend_df.iterrows():
        val = (row["total_fare"] / base_price) * 100
        trend.append({
            "date": row[date_col],
            "value": round(val, 1),
            "isLive": True
        })
        
    return {"trend": trend}

@app.get("/api/fares/raw")
def get_raw_fares():
    daily_path = os.path.join("apix_data", "index", "apix_index_daily.csv")
    if not os.path.exists(daily_path):
        return []
        
    df = pd.read_csv(daily_path)
    if df.empty:
        return []
        
    if "scraped_at" in df.columns:
        # Get the most recent scrape date
        latest_date = df["scraped_at"].str[:10].max()
        df = df[df["scraped_at"].str.startswith(latest_date, na=False)]
        df = df.sort_values(by="scraped_at", ascending=False)
    elif "travel_date" in df.columns:
        latest_date = df["travel_date"].max()
        df = df[df["travel_date"] == latest_date]
        df = df.sort_values(by="travel_date", ascending=False)
        
    latest = df.fillna("").to_dict(orient="records")
    return latest

@app.get("/api/index/heatmap")
def get_heatmap():
    # Priority 6: Sector-wise Heatmap
    daily_path = os.path.join("apix_data", "index", "apix_index_daily.csv")
    if not os.path.exists(daily_path):
        return []
        
    df = pd.read_csv(daily_path)
    if df.empty:
        return []
        
    if "outlier_flag" in df.columns:
        df = df[df["outlier_flag"] == False]
    df = df[df["status"] == "ok"]
    
    if df.empty:
        return []
        
    if "scraped_at" in df.columns:
        df["date"] = df["scraped_at"].str[:10]
    else:
        df["date"] = df["travel_date"]
        
    dates = sorted(df["date"].unique())
    if len(dates) == 0:
        return []
        
    latest_date = dates[-1]
    prev_date = dates[-2] if len(dates) > 1 else None
    
    df["route"] = df["origin"] + "-" + df["destination"]
    
    latest_df = df[df["date"] == latest_date]
    latest_grouped = latest_df.groupby("route")["total_fare"].median()
    
    prev_grouped = pd.Series(dtype=float)
    if prev_date:
        prev_df = df[df["date"] == prev_date]
        prev_grouped = prev_df.groupby("route")["total_fare"].median()
        
    results = []
    for route in latest_grouped.index:
        current_fare = latest_grouped.get(route, 0)
        prev_fare = prev_grouped.get(route, current_fare)
        if prev_fare == 0:
            pct_change = 0
        else:
            pct_change = ((current_fare - prev_fare) / prev_fare) * 100
            
        results.append({
            "route": str(route),
            "pct_change": float(round(pct_change, 2)),
            "current_fare": float(current_fare)
        })
        
    return results

