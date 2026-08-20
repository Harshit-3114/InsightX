import logging
import sqlite3
import sys
from typing import Optional

import pandas as pd

from config import config

logger = logging.getLogger(__name__)


def load_and_clean_data(csv_path: str) -> pd.DataFrame:
    logger.info("Loading dataset from %s...", csv_path)
    df = pd.read_csv(csv_path)

    df.rename(columns={"amount (INR)": "transaction_amount"}, inplace=True)

    df.columns = (
        df.columns.str.strip().str.lower().str.replace(" ", "_")
    )

    logger.info("Total rows loaded: %d", len(df))

    required_columns = [
        "transaction_type",
        "merchant_category",
        "receiver_age_group",
        "fraud_flag",
        "hour_of_day",
        "transaction_amount",
        "transaction_status",
        "device_type",
        "network_type",
        "is_weekend",
    ]

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df.loc[df["transaction_type"] == "P2P", "merchant_category"] = (
        df.loc[df["transaction_type"] == "P2P", "merchant_category"].fillna(
            "N/A (P2P)"
        )
    )

    df.loc[df["transaction_type"] == "P2M", "receiver_age_group"] = (
        df.loc[df["transaction_type"] == "P2M", "receiver_age_group"].fillna(
            "N/A (Merchant)"
        )
    )

    df["fraud_flag"] = df["fraud_flag"].fillna(0).astype(int)
    df["is_weekend"] = df["is_weekend"].astype(int)

    def _categorize_time(hour: int) -> str:
        if 6 <= hour < 12:
            return "Morning"
        if 12 <= hour < 18:
            return "Afternoon"
        if 18 <= hour <= 23:
            return "Peak Evening"
        return "Late Night"

    df["time_block"] = df["hour_of_day"].apply(_categorize_time)
    df["is_high_value"] = (df["transaction_amount"] >= 5000).astype(int)

    return df


def create_database(df: pd.DataFrame, db_path: str) -> None:
    logger.info("Creating SQLite database at %s...", db_path)
    conn = sqlite3.connect(db_path)
    df.to_sql("transactions", conn, if_exists="replace", index=False)
    conn.close()
    logger.info("Database created successfully.")


def run_ground_truth_queries(db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    results = {}

    cursor.execute("""
        SELECT ROUND(
            (SUM(CASE WHEN transaction_status = 'FAILED' THEN 1 ELSE 0 END) * 100.0)
            / COUNT(*), 2
        ) AS failure_rate_percentage
        FROM transactions;
    """)
    results["failure_rate"] = cursor.fetchone()[0]

    cursor.execute("""
        SELECT merchant_category, COUNT(*) as flagged_count
        FROM transactions
        WHERE fraud_flag = 1 AND transaction_type = 'P2M'
        GROUP BY merchant_category
        ORDER BY flagged_count DESC
        LIMIT 3;
    """)
    results["top_flagged_categories"] = cursor.fetchall()

    cursor.execute("""
        SELECT ROUND(
            (SUM(CASE WHEN transaction_status = 'FAILED' THEN 1 ELSE 0 END) * 100.0)
            / COUNT(*), 2
        ) AS android_5g_weekend_failure_rate
        FROM transactions
        WHERE device_type = 'Android' AND network_type = '5G' AND is_weekend = 1;
    """)
    results["android_5g_weekend_failure_rate"] = cursor.fetchone()[0]

    conn.close()
    return results


def main(csv_path: Optional[str] = None, db_path: Optional[str] = None) -> None:
    resolved_csv: str = csv_path if csv_path is not None else config.csv_path
    resolved_db: str = db_path if db_path is not None else config.db_path

    df = load_and_clean_data(resolved_csv)
    create_database(df, resolved_db)
    gt = run_ground_truth_queries(resolved_db)

    print(f"Failure Rate: {gt['failure_rate']}%")
    print(f"Top Flagged Categories: {gt['top_flagged_categories']}")
    print(f"Android/5G/Weekend Failure Rate: {gt['android_5g_weekend_failure_rate']}%")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s: %(message)s"
    )
    main()
