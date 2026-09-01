import os, pandas as pd
df = pd.read_csv("apix_data/index/apix_index_daily.csv")
latest_date = df["scraped_at"].str[:10].max()
df = df[df["scraped_at"].str.startswith(latest_date, na=False)]
route_df = df[(df["origin"] == "BLR") & (df["destination"] == "HYD") & (df["status"] == "ok") & (df["outlier_flag"] == False)]
for days in [1, 7, 15, 30, 45]:
    subset = route_df[route_df["advance_purchase_days"] == days]
    print(f"T+{days}: {len(subset)} ok quotes")
