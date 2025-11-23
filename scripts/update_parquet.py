"""Utility script to maintain a historical Parquet store of listing snapshots.

The script reads a JSON Lines file that contains listing records with a
``captured_at`` timestamp, deduplicates entries for the same listing within a
single day, and appends new unique records to a Parquet file that serves as the
master data store. Existing Parquet data is preserved so historical snapshots
across days remain intact.
"""

from __future__ import annotations

import argparse
import os

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Deduplicate listing JSONL data by (listing_id, captured_date) and append "
            "new records to a Parquet history file."
        )
    )
    parser.add_argument(
        "jsonl_path",
        help="Path to the source JSON Lines file containing listing data.",
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
        existing["captured_at"] = pd.to_datetime(existing["captured_at"], errors="coerce")
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


def main():
    jsonl_path = os.path.join("data_streams", "scrape_session_20251123T033924.jsonl")
    parquet_path = os.path.join("data_streams", "data.parquet")

    new_data = load_jsonl(jsonl_path)
    existing = load_existing_parquet(parquet_path)
    updated = append_new_records(new_data, existing)
    save_parquet(updated, parquet_path)


if __name__ == "__main__":
    main()