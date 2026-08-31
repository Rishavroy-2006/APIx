import os
import glob
import pandas as pd
from datetime import datetime, timezone

def compute_index(target_date_str=None):
    if not target_date_str:
        # Default to today in UTC (matching the scraping timezone convention)
        target_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    raw_dir = os.path.join("apix_data", "raw", target_date_str)
    index_file = os.path.join("apix_data", "index", "apix_index_daily.csv")
    
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
    # If the same flight was scraped multiple times today (e.g. morning and evening batch), 
    # keep the one with the most recent 'scraped_at' timestamp.
    # We group by the unique flight signature + fare class.
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

    # 4. Merge into master index
    os.makedirs(os.path.dirname(index_file), exist_ok=True)
    
    if os.path.exists(index_file):
        master_df = pd.read_csv(index_file)
        # Extract just the date part from scraped_at to remove any existing entries for this target_date
        # This makes the script idempotent (safe to run multiple times a day)
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
    
    # Save
    master_df.to_csv(index_file, index=False)
    print(f"Successfully saved {len(master_df)} total records to {index_file}.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Compile daily raw scrapes into master index.")
    parser.add_argument("--date", type=str, help="Date to process in YYYY-MM-DD format (defaults to today UTC).")
    args = parser.parse_args()
    
    compute_index(args.date)
