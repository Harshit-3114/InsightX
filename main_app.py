import logging
import re
import sqlite3

from text_to_sql_engine import (
    extract_sql,
    generate_insight_from_data,
    generate_sql_from_nvidia,
)

logger = logging.getLogger(__name__)


def autocorrect_insight(insight: str, sql_query: str, results: list) -> str:
    if not results or not results[0]:
        return insight

    actual_value = results[0][0]
    aggregate_keywords = ["MIN(", "MAX(", "AVG(", "COUNT(", "SUM("]

    if any(kw in sql_query.upper() for kw in aggregate_keywords):
        corrected = re.sub(r"\d+(\.\d+)?", str(actual_value), insight, count=1)
        return corrected

    return insight


def run_query(user_input: str) -> None:
    try:
        raw_response = generate_sql_from_nvidia(user_input)
        sql_queries = extract_sql(raw_response)

        if not sql_queries or not sql_queries[0]:
            print("Error: Could not extract SQL query from AI response.")
            return

        conn = sqlite3.connect("file:transactions.db?mode=ro", uri=True)
        cursor = conn.cursor()

        all_results = []
        for i, sql_query in enumerate(sql_queries):
            if len(sql_queries) > 1:
                print(f"\n--- Query {i+1} ---")
            cursor.execute(sql_query)
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            all_results.append((sql_query, columns, results))

            print(f"\nSQL: {sql_query}")
            print("Results:")
            for row in results:
                for col, val in zip(columns, row):
                    print(f"  {col}: {val}")

        conn.close()

        if all_results:
            flat_results = "\n".join(
                str(r[2]) for r in all_results
            )
            insight = generate_insight_from_data(user_input, flat_results)

            primary_sql = sql_queries[0]
            primary_results = all_results[0][2]
            insight = autocorrect_insight(insight, primary_sql, primary_results)

            print("\nAI Insight:")
            print("-" * 40)
            print(insight)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s: %(message)s"
    )
    print("--- InsightX Analytics CLI ---")
    question = input("Ask a question about your transactions: ")
    run_query(question)
