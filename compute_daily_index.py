import os
import glob
import pandas as pd
from datetime import datetime, timezone

# DGCA traffic-style estimated weights for the 6 active routes.
# Sum = 0.90 pre-normalization. The composite calculation at line ~170
# divides by total_weight (the sum of weights for routes that reported data),
# which automatically re-normalizes to 1.0 even when routes are missing.
# These are estimated placeholder values — in production, replace with exact
# passenger-volume figures from DGCA's official monthly traffic reports.
DGCA_ROUTE_WEIGHTS = {
    "DEL-BOM": 0.25,
    "DEL-BLR": 0.20,
    "BOM-BLR": 0.15,
    "DEL-CCU": 0.10,
    "BLR-HYD": 0.10,
    "MAA-DEL": 0.10,
}

def compute_index(target_date_str=None):
    if not target_date_str:
        # Default to today in UTC (matching the scraping timezone convention)
        target_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    raw_dir = os.path.join("apix_data", "raw", target_date_str)
    index_file = os.path.join("apix_data", "index", "apix_index_daily.csv")
    composite_index_file = os.path.join("apix_data", "index", "apix_composite_index.csv")
    
    if not os.path.exists(raw_dir):
        print(f"No raw data directory found for {target_date_str}: {raw_dir}")
        return

    # 1. Load all raw CSVs for the day
    all_files = glob.glob(os.path.join(raw_dir, "*.csv"))
    if not all_files:
        print(f"No CSV files found in {raw_dir}")
        return

    print(f"Found {len(all_files)} raw CSVs for {target_date_str}. Processing...")
    
    df_list = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            df_list.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if not df_list:
        return
        
    daily_df = pd.concat(df_list, ignore_index=True)
    
    # 2. We keep all records (including sold_out/parse_error) to maintain auditability.
    # We just drop duplicates.
    
    # 3. Deduplicate
    dedup_keys = [
        "origin", "destination", "carrier_code", "flight_num", 
        "travel_date", "advance_purchase_days", "fare_class"
    ]
    
    # Sort by scraped_at descending so the first one is the newest
    daily_df = daily_df.sort_values(by="scraped_at", ascending=False)
    daily_df = daily_df.drop_duplicates(subset=dedup_keys, keep="first")
    
    print(f"After deduplication, {len(daily_df)} unique flight quotes remain for {target_date_str}.")
    
    # Normalize fare_class to lowercase — scrapers may write 'Economy' or 'economy'
    # This must happen before any fare_class filter is applied (outlier calc, index math)
    if 'fare_class' in daily_df.columns:
        daily_df['fare_class'] = daily_df['fare_class'].str.lower()

    if len(daily_df) == 0:
        print("No valid data to index.")
        return

    print("Applying IQR & Plausibility outlier removal...")
    
    # Pre-calculate historical maxes per route
    historical_maxes = {}
    if os.path.exists(index_file):
        try:
            hist_df = pd.read_csv(index_file)
            if 'outlier_flag' in hist_df.columns:
                hist_df = hist_df[hist_df['outlier_flag'] == False]
            hist_df['route'] = hist_df['origin'] + "-" + hist_df['destination']
            historical_maxes = hist_df.groupby('route')['total_fare'].max().to_dict()
        except Exception as e:
            pass
            
    def get_lower(x):
        x = x.dropna()
        if len(x) < 4: return 500
        q1 = x.quantile(0.25)
        q3 = x.quantile(0.75)
        return min(q1 - 1.5 * (q3 - q1), 500)
        
    def get_upper(x):
        x = x.dropna()
        if len(x) < 4: return -1
        q1 = x.quantile(0.25)
        q3 = x.quantile(0.75)
        return q3 + 1.5 * (q3 - q1)

    gb = daily_df[daily_df['status'] == 'ok'].groupby(['origin', 'destination', 'advance_purchase_days'])['total_fare']
    bounds_df = gb.agg(
        lower_bound=get_lower,
        upper_bound=get_upper
    ).reset_index()
    
    bounds_df['route'] = bounds_df['origin'] + "-" + bounds_df['destination']
    mask = bounds_df['upper_bound'] == -1
    if mask.any():
        bounds_df.loc[mask, 'upper_bound'] = bounds_df.loc[mask, 'route'].map(lambda r: historical_maxes.get(r, 20000)) * 10
    bounds_df = bounds_df.drop(columns=['route'])
    
    daily_df = daily_df.merge(bounds_df, on=['origin', 'destination', 'advance_purchase_days'], how='left')
    
    daily_df['outlier_flag'] = False
    out_of_bounds = (daily_df['status'] == 'ok') & ((daily_df['total_fare'] < daily_df['lower_bound']) | (daily_df['total_fare'] > daily_df['upper_bound']))
    daily_df.loc[out_of_bounds, 'outlier_flag'] = True
    daily_df = daily_df.drop(columns=['lower_bound', 'upper_bound'])
    
    outlier_count = daily_df['outlier_flag'].sum()
    print(f"Flagged {outlier_count} glitch/outlier fares via IQR.")

    # 4. Merge into master index
    os.makedirs(os.path.dirname(index_file), exist_ok=True)
    
    if os.path.exists(index_file):
        master_df = pd.read_csv(index_file)
        # Extract just the date part from scraped_at to remove any existing entries for this target_date
        # This makes the script idempotent
        master_df["_scrape_date"] = master_df["scraped_at"].str[:10]
        original_len = len(master_df)
        master_df = master_df[master_df["_scrape_date"] != target_date_str]
        master_df = master_df.drop(columns=["_scrape_date"])
        
        print(f"Removed {original_len - len(master_df)} existing records for {target_date_str} from master index to avoid duplication.")
        
        # Append new data
        master_df = pd.concat([master_df, daily_df], ignore_index=True)
    else:
        print("Master index does not exist. Creating new one.")
        master_df = daily_df
        
    # Sort master index for neatness
    master_df = master_df.sort_values(by=["scraped_at", "origin", "destination", "advance_purchase_days"])
    master_df.to_csv(index_file, index=False)
    print(f"Successfully saved {len(master_df)} total records to {index_file}.")

    # 5. Compute Daily Weighted Composite Index (Laspeyres-style)
    print("Computing Weighted Composite Fare Index...")
    if 'source' not in daily_df.columns:
        daily_df['source'] = 'airline_direct'

    # Compute OTA Premium per horizon
    premium_dict = {}
    ota_df = daily_df[(daily_df['status'] == 'ok') & (daily_df['source'] == 'ota') & (daily_df['outlier_flag'] == False)]
    # Exclude unvalidated/incidental carriers (Air India Express) from the core math
    math_df = daily_df[(daily_df['status'] == 'ok') & (daily_df['source'] == 'airline_direct') & (daily_df['outlier_flag'] == False) & (daily_df['carrier_name'] != 'Air India Express')]
    
    if not ota_df.empty:
        ota_grp = ota_df.groupby(['origin', 'destination', 'flight_num', 'advance_purchase_days'])['total_fare'].median().reset_index(name='ota_fare')
        dir_grp = math_df.groupby(['origin', 'destination', 'flight_num', 'advance_purchase_days'])['total_fare'].median().reset_index(name='dir_fare')
        m = pd.merge(ota_grp, dir_grp, on=['origin', 'destination', 'flight_num', 'advance_purchase_days'])
        if not m.empty:
            m['premium_pct'] = ((m['ota_fare'] - m['dir_fare']) / m['dir_fare']) * 100
            premium_dict = m.groupby('advance_purchase_days')['premium_pct'].mean().to_dict()

    median_fares = math_df.groupby(['origin', 'destination', 'advance_purchase_days'])['total_fare'].median().reset_index()
    
    composite_rows = []
    horizons = median_fares['advance_purchase_days'].unique()
    
    for h in horizons:
        h_df = median_fares[median_fares['advance_purchase_days'] == h]
        
        weighted_sum = 0
        total_weight = 0
        
        for _, row in h_df.iterrows():
            route_key = f"{row['origin']}-{row['destination']}"
            if route_key in DGCA_ROUTE_WEIGHTS:
                weight = DGCA_ROUTE_WEIGHTS[route_key]
                weighted_sum += row['total_fare'] * weight
                total_weight += weight
                
        if total_weight > 0:
            # Re-normalize if some routes are missing
            composite_score = weighted_sum / total_weight
            composite_rows.append({
                "date": target_date_str,
                "advance_purchase_days": h,
                "composite_score": round(composite_score, 2),
                "ota_premium_pct": round(premium_dict.get(h, 0.0), 2)
            })
            
    if composite_rows:
        composite_df = pd.DataFrame(composite_rows)
        if os.path.exists(composite_index_file):
            master_comp_df = pd.read_csv(composite_index_file)
            master_comp_df = master_comp_df[master_comp_df['date'] != target_date_str]
            master_comp_df = pd.concat([master_comp_df, composite_df], ignore_index=True)
        else:
            master_comp_df = composite_df
            
        master_comp_df = master_comp_df.sort_values(by=["date", "advance_purchase_days"])
        master_comp_df.to_csv(composite_index_file, index=False)
        print(f"Saved daily composite index to {composite_index_file}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Compile daily raw scrapes into master index.")
    parser.add_argument("--date", type=str, help="Date to process in YYYY-MM-DD format (defaults to today UTC).")
    args = parser.parse_args()
    
    compute_index(args.date)

