"""Utility script to maintain a historical Parquet store of listing snapshots.

The script reads all JSON Lines files in a directory that contain listing records
with a ``captured_at`` timestamp, deduplicates entries for the same listing
within a single day, and appends new unique records to a Parquet file that
serves as the master data store. Existing Parquet data is preserved so historical
snapshots across days remain intact.
"""

from __future__ import annotations

import argparse
import os
from glob import glob

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Deduplicate listing JSONL data by (listing_id, captured_date) and append "
            "new records from all JSONL files in a directory to a Parquet history file."
        )
    )
    parser.add_argument(
        "jsonl_dir",
        help="Path to the directory containing JSON Lines files with listing data.",
    )
    parser.add_argument(
        "parquet_path",
        help="Path to the Parquet file that stores the historical listing data.",
    )
    return parser.parse_args()


def _ensure_required_columns(df: pd.DataFrame) -> None:
    required = {"listing_id", "captured_at"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in JSONL data: {sorted(missing)}")


def _deduplicate_new_data(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate incoming data on (listing_id, captured_date).

    For rows with the same listing on the same day, the latest ``captured_at``
    timestamp is kept.
    """

    _ensure_required_columns(df)
    df = df.copy()
    df["captured_at"] = pd.to_datetime(df["captured_at"], errors="coerce")

    if df["captured_at"].isna().any():
        raise ValueError("One or more rows have invalid 'captured_at' timestamps.")

    df["captured_date"] = df["captured_at"].dt.normalize()
    df.sort_values("captured_at", inplace=True)
    deduped = df.drop_duplicates(subset=["listing_id", "captured_date"], keep="last")
    return deduped


def load_jsonl(jsonl_path: str) -> pd.DataFrame:
    if not os.path.exists(jsonl_path):
        raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")

    df = pd.read_json(jsonl_path, lines=True)
    if df.empty:
        return df
    return _deduplicate_new_data(df)


def load_existing_parquet(parquet_path: str) -> pd.DataFrame:
    if not os.path.exists(parquet_path):
        return pd.DataFrame()

    existing = pd.read_parquet(parquet_path)
    if "captured_at" in existing.columns:
        existing["captured_at"] = pd.to_datetime(
            existing["captured_at"], errors="coerce"
        )
    if "captured_date" in existing.columns:
        existing["captured_date"] = pd.to_datetime(
            existing["captured_date"], errors="coerce"
        )
    return existing


def append_new_records(new_data: pd.DataFrame, existing: pd.DataFrame) -> pd.DataFrame:
    if new_data.empty:
        return existing

    new_keys = set(zip(new_data["listing_id"], new_data["captured_date"]))

    if existing.empty:
        return new_data

    existing_keys = set(zip(existing["listing_id"], existing["captured_date"]))
    has_overlap = bool(new_keys & existing_keys)

    if has_overlap:
        mask_existing = [
            (listing_id, captured_date) not in new_keys
            for listing_id, captured_date in zip(
                existing["listing_id"], existing["captured_date"]
            )
        ]
        existing = existing.loc[mask_existing]

    return pd.concat([existing, new_data], ignore_index=True)


def save_parquet(df: pd.DataFrame, parquet_path: str) -> None:
    df.to_parquet(parquet_path, index=False)


def iter_jsonl_files(jsonl_dir: str):
    """Yield all JSONL file paths in the directory, sorted by name."""
    pattern = os.path.join(jsonl_dir, "*.jsonl")
    for path in sorted(glob(pattern)):
        if os.path.isfile(path):
            yield path


def main():
    args = parse_args()
    jsonl_dir = args.jsonl_dir
    parquet_path = args.parquet_path

    existing = load_existing_parquet(parquet_path)

    for jsonl_path in iter_jsonl_files(jsonl_dir):
        new_data = load_jsonl(jsonl_path)
        existing = append_new_records(new_data, existing)

    # After processing all JSONL files, write the final deduplicated store
    save_parquet(existing, parquet_path)


if __name__ == "__main__":
    main()

#Run with python scripts/update_parquet.py data_streams data_streams/data.parquet
