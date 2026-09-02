import os
import glob
import logging
import pandas as pd
from typing import List, Dict, Tuple

from core.fare_schema import normalize_row, FareQuote

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

RAW_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "apix_data", "raw")
PROCESSED_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "apix_data", "processed")
PARQUET_PATH = os.path.join(PROCESSED_DATA_DIR, "fare_quotes_master.parquet")

DEDUP_KEYS = ["origin", "destination", "flight_num", "travel_date", "capture_run", "source_scraper"]


def infer_source_scraper(filename: str) -> str:
    """Infer scraper identifier from filename."""
    base = os.path.basename(filename).lower()
    if base.startswith("indigo"):
        return "indigo"
    elif base.startswith("air_india"):
        return "air_india"
    elif base.startswith("spicejet"):
        return "spicejet"
    elif base.startswith("akasa"):
        return "akasa"
    elif base.startswith("makemytrip") or base.startswith("mmt"):
        return "makemytrip"
    elif base.startswith("goibibo"):
        return "goibibo"
    else:
        return base.split("_raw")[0].split("_20")[0]


def ingest_raw_csvs(raw_dir: str = RAW_DATA_DIR, parquet_path: str = PARQUET_PATH) -> pd.DataFrame:
    """
    Walks raw_dir for CSV files, normalizes each row into a FareQuote model,
    tags with source_scraper and source_file, and writes/appends deduplicated rows
    to parquet_path. Prints summary of read, normalized, and rejected rows.
    """
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)

    csv_files = glob.glob(os.path.join(raw_dir, "**", "*.csv"), recursive=True)
    csv_files.sort()

    total_rows_read = 0
    total_rows_normalized = 0
    rejections: List[Tuple[str, str, str]] = []  # (source_file, error_message, raw_row_str)

    normalized_quotes: List[dict] = []

    print(f"\n{'='*70}")
    print(f"  APIx Data Ingestion Pipeline")
    print(f"{'='*70}")
    print(f"Found {len(csv_files)} raw CSV file(s) under '{raw_dir}'.\n")

    for filepath in csv_files:
        rel_path = os.path.relpath(filepath, start=os.path.dirname(raw_dir))
        scraper_id = infer_source_scraper(filepath)

        try:
            df = pd.read_csv(filepath, dtype=str)
        except Exception as e:
            logger.error(f"Could not read CSV '{filepath}': {e}")
            rejections.append((rel_path, f"CSV read error: {e}", "FILE_LEVEL"))
            continue

        file_row_count = len(df)
        total_rows_read += file_row_count

        for idx, row in df.iterrows():
            raw_dict = row.to_dict()
            try:
                quote: FareQuote = normalize_row(raw_dict, source_scraper=scraper_id)
                quote_dict = quote.model_dump()
                quote_dict["source_file"] = rel_path
                normalized_quotes.append(quote_dict)
                total_rows_normalized += 1
            except Exception as e:
                rejections.append((rel_path, str(e), str(raw_dict)))

    print(f"Rows Read: {total_rows_read}")
    print(f"Rows Normalized: {total_rows_normalized}")
    print(f"Rows Rejected: {len(rejections)}")

    if rejections:
        print("\nRejection Reasons Breakdown:")
        reason_counts: Dict[str, int] = {}
        for _, err, _ in rejections:
            short_err = err.split(" | ")[0]
            reason_counts[short_err] = reason_counts.get(short_err, 0) + 1
        for reason, count in reason_counts.items():
            print(f"  - {reason}: {count} row(s)")

    if not normalized_quotes:
        print("\nNo normalized quotes to save.")
        if os.path.exists(parquet_path):
            return pd.read_parquet(parquet_path)
        return pd.DataFrame()

    new_df = pd.DataFrame(normalized_quotes)

    # Load existing parquet dataset if present for deduplication
    existing_count = 0
    if os.path.exists(parquet_path):
        try:
            existing_df = pd.read_parquet(parquet_path)
            existing_count = len(existing_df)
            print(f"\nExisting master parquet has {existing_count} rows.")

            # Anti-join / filter out duplicates on DEDUP_KEYS
            existing_keys = set(zip(*[existing_df[k].astype(str) for k in DEDUP_KEYS]))
            new_keys = list(zip(*[new_df[k].astype(str) for k in DEDUP_KEYS]))

            mask = [k not in existing_keys for k in new_keys]
            dedup_df = new_df[mask].copy()
            added_count = len(dedup_df)
            print(f"New unique rows to append: {added_count} (skipped {len(new_df) - added_count} existing duplicates)")

            if added_count > 0:
                final_df = pd.concat([existing_df, dedup_df], ignore_index=True)
            else:
                final_df = existing_df
        except Exception as e:
            logger.warning(f"Error reading existing parquet, overwriting: {e}")
            final_df = new_df
            added_count = len(new_df)
    else:
        final_df = new_df
        added_count = len(new_df)
        print(f"\nCreating new master parquet with {added_count} rows.")

    final_df.to_parquet(parquet_path, index=False, engine="pyarrow")
    print(f"Successfully saved master dataset to '{parquet_path}' ({len(final_df)} total rows).")
    print(f"{'='*70}\n")

    return final_df


run = ingest_raw_csvs

if __name__ == "__main__":
    ingest_raw_csvs()
