import os
import glob
import pandas as pd
from datetime import datetime, timezone

# Approximate DGCA traffic weights for the 8 core routes
DGCA_ROUTE_WEIGHTS = {
    "DEL-BOM": 0.25,
    "DEL-BLR": 0.20,
    "BOM-BLR": 0.15,
    "DEL-CCU": 0.10,
    "BLR-HYD": 0.10,
    "MAA-DEL": 0.10,
    "DEL-PNQ": 0.05,
    "BOM-GOI": 0.05
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
    
    # 2. Filter out errors/no_flights
    initial_len = len(daily_df)
    daily_df = daily_df[daily_df["status"] == "ok"]
    print(f"Filtered out {initial_len - len(daily_df)} non-ok records.")
    
    # 3. Deduplicate
    dedup_keys = [
        "origin", "destination", "carrier_code", "flight_num", 
        "travel_date", "advance_purchase_days", "fare_class"
    ]
    
    # Sort by scraped_at descending so the first one is the newest
    daily_df = daily_df.sort_values(by="scraped_at", ascending=False)
    daily_df = daily_df.drop_duplicates(subset=dedup_keys, keep="first")
    
    print(f"After deduplication, {len(daily_df)} unique flight quotes remain for {target_date_str}.")
    
    if len(daily_df) == 0:
        print("No valid data to index.")
        return

    # 3.1. Statistical Outlier Removal (IQR)
    print("Applying IQR outlier removal...")
    pre_outlier_len = len(daily_df)
    
    def get_lower(x):
        if len(x) < 4: return -9999999
        q1 = x.quantile(0.25)
        q3 = x.quantile(0.75)
        return q1 - 1.5 * (q3 - q1)
        
    def get_upper(x):
        if len(x) < 4: return 9999999
        q1 = x.quantile(0.25)
        q3 = x.quantile(0.75)
        return q3 + 1.5 * (q3 - q1)

    gb = daily_df.groupby(['origin', 'destination', 'advance_purchase_days'])['total_fare']
    daily_df['lower_bound'] = gb.transform(get_lower)
    daily_df['upper_bound'] = gb.transform(get_upper)
    
    daily_df = daily_df[(daily_df['total_fare'] >= daily_df['lower_bound']) & (daily_df['total_fare'] <= daily_df['upper_bound'])]
    daily_df = daily_df.drop(columns=['lower_bound', 'upper_bound'])
    
    print(f"Removed {pre_outlier_len - len(daily_df)} glitch/outlier fares via IQR.")
    
    if len(daily_df) == 0:
        print("No valid data to index after outlier removal.")
        return

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
    medians = daily_df.groupby(['origin', 'destination', 'advance_purchase_days'])['total_fare'].median().reset_index()
    
    composite_rows = []
    horizons = medians['advance_purchase_days'].unique()
    
    for h in horizons:
        h_df = medians[medians['advance_purchase_days'] == h]
        
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
                "composite_score": round(composite_score, 2)
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

