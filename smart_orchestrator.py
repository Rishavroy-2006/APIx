import os
import glob
import pandas as pd
from datetime import datetime, timezone
import subprocess

def get_completed_horizons(carrier_code, date_str):
    raw_dir = os.path.join("apix_data", "raw", date_str)
    if not os.path.exists(raw_dir):
        return set()
    
    csvs = glob.glob(os.path.join(raw_dir, "*.csv"))
    completed = set()
    for f in csvs:
        try:
            df = pd.read_csv(f)
            # Filter for this carrier
            df_carrier = df[df['carrier_code'] == carrier_code]
            if not df_carrier.empty:
                # Add all unique advance_purchase_days
                completed.update(df_carrier['advance_purchase_days'].unique().tolist())
        except Exception as e:
            print(f"Error reading {f}: {e}")
    return completed

def run_scraper(scraper_path, windows_set):
    if not windows_set:
        return
    
    windows_str = ",".join(map(str, sorted(windows_set)))
    print(f"\n========================================================")
    print(f"🚀 Running {scraper_path} for missing windows: {windows_str}")
    print(f"========================================================")
    
    # Run the scraper with xvfb (Virtual Display required for undetected_chromedriver on GitHub Actions)
    # We use a list format for subprocess for safer execution
    cmd = ["xvfb-run", "python3", scraper_path, "--windows", windows_str]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Scraper {scraper_path} exited with error code {e.returncode}")
    except FileNotFoundError:
        # Fallback if xvfb-run is not installed (e.g. running locally on Mac)
        print("xvfb-run not found, running directly (assuming local machine with display)")
        cmd = ["python3", scraper_path, "--windows", windows_str]
        subprocess.run(cmd, check=True)

def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    required = {1, 7, 15, 30, 45}
    
    print(f"🔍 Checking APIx Data State for {today}")
    
    # Check SpiceJet (SG)
    sg_completed = get_completed_horizons("SG", today)
    sg_missing = required - sg_completed
    print(f"  -> SpiceJet (SG) completed: {sg_completed}")
    print(f"  -> SpiceJet (SG) missing:   {sg_missing}")
    
    # Check IndiGo (6E)
    ig_completed = get_completed_horizons("6E", today)
    ig_missing = required - ig_completed
    print(f"  -> IndiGo (6E) completed:   {ig_completed}")
    print(f"  -> IndiGo (6E) missing:     {ig_missing}")
    
    if not sg_missing and not ig_missing:
        print("\n✅ All Required Data for today has been collected! Exiting gracefully.")
        return
        
    # Execute missing scrapes
    run_scraper("spicejet/spicejet_scraper.py", sg_missing)
    run_scraper("indigo/indigo_scraper_uc.py", ig_missing)
    
    print("\n✅ Orchestrator execution complete.")

if __name__ == "__main__":
    main()
