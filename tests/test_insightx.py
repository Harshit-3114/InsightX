"""Tests for the InsightX query engine.

The LLM path needs an NVIDIA NIM key, so these tests cover everything around
it: the data pipeline, the SQL parsing, the SQL safety checks and the
read-only database connection. The parts that need a key are left alone.
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import data_engine  # noqa: E402
from text_to_sql_engine import extract_sql  # noqa: E402


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    """Run the seed script in a temp directory and return the CSV path."""
    workdir = tmp_path_factory.mktemp("data")
    subprocess.run(
        [sys.executable, str(ROOT / "seed_data.py")],
        cwd=str(workdir),
        check=True,
        capture_output=True,
    )
    return workdir / "insightx_transactions.csv"


@pytest.fixture(scope="module")
def cleaned(dataset):
    return data_engine.load_and_clean_data(str(dataset))


@pytest.fixture(scope="module")
def built_db(cleaned, tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "transactions.db"
    data_engine.create_database(cleaned, str(db_path))
    return db_path


class TestSeedData:
    def test_the_dataset_has_five_thousand_rows(self, dataset):
        import pandas as pd

        df = pd.read_csv(dataset)
        assert len(df) == 5000

    def test_the_seed_is_reproducible(self, dataset, tmp_path):
        # seed_data.py uses random.seed(42), so a second run is identical.
        subprocess.run(
            [sys.executable, str(ROOT / "seed_data.py")],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
        )
        second = tmp_path / "insightx_transactions.csv"
        assert second.read_bytes() == dataset.read_bytes()


class TestLoadAndClean:
    def test_the_row_count_survives_cleaning(self, cleaned):
        assert len(cleaned) == 5000

    def test_column_names_are_normalised(self, cleaned):
        assert "amount (INR)" not in cleaned.columns
        assert "transaction_amount" in cleaned.columns

    def test_derived_columns_are_added(self, cleaned):
        for col in ("time_block", "is_high_value"):
            assert col in cleaned.columns

    def test_time_blocks_are_labelled(self, cleaned):
        assert set(cleaned["time_block"]) <= {
            "Morning",
            "Afternoon",
            "Peak Evening",
            "Late Night",
        }

    def test_high_value_uses_a_five_thousand_threshold(self, cleaned):
        high = cleaned[cleaned["is_high_value"] == 1]
        assert (high["transaction_amount"] >= 5000).all()
        low = cleaned[cleaned["is_high_value"] == 0]
        assert (low["transaction_amount"] < 5000).all()

    def test_p2p_rows_get_a_merchant_category_placeholder(self, cleaned):
        p2p = cleaned[cleaned["transaction_type"] == "P2P"]
        assert (p2p["merchant_category"] == "N/A (P2P)").all()

    def test_p2m_rows_get_an_age_placeholder(self, cleaned):
        p2m = cleaned[cleaned["transaction_type"] == "P2M"]
        assert (p2m["receiver_age_group"] == "N/A (Merchant)").all()

    def test_a_csv_missing_required_columns_is_rejected(self, tmp_path):
        bad = tmp_path / "bad.csv"
        bad.write_text("transaction_id,amount\nTXN1,100\n")
        with pytest.raises(ValueError, match="Missing required columns"):
            data_engine.load_and_clean_data(str(bad))


class TestDatabase:
    def test_the_database_is_created(self, built_db):
        assert built_db.exists()
        conn = sqlite3.connect(str(built_db))
        try:
            count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        finally:
            conn.close()
        assert count == 5000

    def test_the_ground_truth_queries_run(self, built_db):
        gt = data_engine.run_ground_truth_queries(str(built_db))
        assert 0 < gt["failure_rate"] < 100
        assert len(gt["top_flagged_categories"]) == 3
        assert 0 < gt["android_5g_weekend_failure_rate"] < 100

    def test_ground_truth_results_are_reproducible(self, built_db):
        first = data_engine.run_ground_truth_queries(str(built_db))
        second = data_engine.run_ground_truth_queries(str(built_db))
        assert first == second


class TestExtractSql:
    def test_a_plain_query_is_returned_as_is(self):
        assert extract_sql("SELECT * FROM transactions") == ["SELECT * FROM transactions"]

    def test_markdown_fences_are_stripped(self):
        raw = "```sql\nSELECT COUNT(*) FROM transactions;\n```"
        assert extract_sql(raw) == ["SELECT COUNT(*) FROM transactions"]

    def test_the_sql_label_is_stripped(self):
        raw = "SQL:\nSELECT 1 FROM transactions"
        assert extract_sql(raw) == ["SELECT 1 FROM transactions"]

    def test_multiple_queries_are_split_on_the_delimiter(self):
        raw = "SELECT 1 FROM transactions;--Q--;SELECT 2 FROM transactions"
        assert extract_sql(raw) == [
            "SELECT 1 FROM transactions",
            "SELECT 2 FROM transactions",
        ]

    def test_a_trailing_semicolon_is_removed(self):
        assert extract_sql("SELECT 1 FROM transactions;") == ["SELECT 1 FROM transactions"]

    def test_an_empty_response_returns_an_empty_query(self):
        assert extract_sql("") == [""]

    def test_the_result_is_always_a_list(self):
        assert isinstance(extract_sql("SELECT 1"), list)


class TestSqlSafety:
    """The validation lives in app.py, which is a Streamlit script."""

    @pytest.fixture(scope="class")
    def validate(self):
        try:
            import app  # noqa: F401
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"app.py could not be imported for testing: {exc}")
        return app._validate_sql

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM transactions",
            "select count(*) from transactions",
            "WITH t AS (SELECT 1) SELECT * FROM t",
            "EXPLAIN SELECT 1",
        ],
    )
    def test_read_only_queries_are_allowed(self, validate, sql):
        assert validate(sql) is True

    @pytest.mark.parametrize(
        "sql",
        [
            "DROP TABLE transactions",
            "DELETE FROM transactions",
            "INSERT INTO transactions VALUES (1)",
            "UPDATE transactions SET amount = 0",
            "ALTER TABLE transactions ADD COLUMN x TEXT",
            "CREATE TABLE evil (id INT)",
            "ATTACH DATABASE 'other.db' AS other",
            "PRAGMA table_info(transactions)",
            "VACUUM",
            "REINDEX",
        ],
    )
    def test_mutating_statements_are_rejected(self, validate, sql):
        assert validate(sql) is False

    def test_an_empty_query_is_rejected(self, validate):
        assert validate("") is False
        assert validate("   ") is False


class TestReadOnlyConnection:
    def test_the_connection_refuses_writes(self, built_db):
        abs_path = os.path.abspath(str(built_db))
        conn = sqlite3.connect(f"file:{abs_path}?mode=ro", uri=True)
        try:
            with pytest.raises(sqlite3.OperationalError):
                conn.execute("DELETE FROM transactions")
        finally:
            conn.close()

    def test_a_missing_database_raises_a_clear_error(self, tmp_path):
        abs_path = os.path.abspath(str(tmp_path / "nope.db"))
        with pytest.raises(sqlite3.OperationalError):
            sqlite3.connect(f"file:{abs_path}?mode=ro", uri=True)
