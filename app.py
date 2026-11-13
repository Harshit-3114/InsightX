import hashlib
import logging
import os
import sqlite3
import time
from io import StringIO
from typing import Optional

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from config import config
from text_to_sql_engine import (
    extract_sql,
    generate_insight_from_data,
    generate_sql_from_nvidia,
)

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="InsightX Analytics",
    page_icon="\U0001f4ca",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── Session State ──
for key, default in {
    "query_history": [],
    "cache": {},
    "query_timestamps": [],
    "conversation": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Custom CSS ──
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"], [class*="st-"] {
        font-family: 'Inter', sans-serif !important;
    }
    .main-header {
        text-align: center;
        font-weight: 700;
        font-size: 2.5rem;
        letter-spacing: -0.5px;
        margin: 0.5rem 0 0.25rem 0;
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .sub-header {
        text-align: center;
        font-size: 0.95rem;
        color: #6b7280;
        margin-bottom: 1.5rem;
    }
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 500 !important;
    }
    [data-testid="stForm"] {
        border-radius: 16px !important;
        padding: 24px !important;
        background-color: #f8f9fa !important;
        border: 1px solid #e5e7eb !important;
        transition: background-color 0.3s ease;
    }
    [data-testid="stFormSubmitButton"] > button {
        border-radius: 12px !important;
        background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
        color: white !important;
        border: none !important;
        font-weight: 500 !important;
        padding: 0.5rem 2rem !important;
        width: 100%;
        transition: opacity 0.2s ease;
    }
    [data-testid="stFormSubmitButton"] > button:hover {
        opacity: 0.9;
    }
    div[data-baseweb="input"] > div {
        border-radius: 12px !important;
    }
    .conv-turn {
        padding: 0.5rem 0;
        border-bottom: 1px solid #e5e7eb;
    }
    .conv-q {
        font-weight: 500;
        color: #3b82f6;
    }
    .conv-a {
        color: #374151;
        font-size: 0.85rem;
    }
    @media (prefers-color-scheme: dark) {
        [data-testid="stForm"] {
            background-color: #1e1e1e !important;
            border-color: #333 !important;
        }
        .sub-header { color: #9ca3af !important; }
        .conv-a { color: #d1d5db !important; }
    }
</style>
""",
    unsafe_allow_html=True,
)

# ── Utility ──


def _cache_key(query: str) -> str:
    return hashlib.md5(query.strip().lower().encode()).hexdigest()


def _check_rate_limit() -> bool:
    now = time.time()
    cutoff = now - 60
    st.session_state.query_timestamps = [
        t for t in st.session_state.query_timestamps if t > cutoff
    ]
    if len(st.session_state.query_timestamps) >= config.rate_limit_per_minute:
        return False
    st.session_state.query_timestamps.append(now)
    return True


def _format_currency(val: object) -> object:
    if isinstance(val, (int, float)):
        return f"\u20b9{val:,.2f}"
    return val


def _get_readonly_connection(path: str) -> sqlite3.Connection:
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(
            f"Database file '{path}' not found. "
            "Run `python data_engine.py` first to create it."
        )
    return sqlite3.connect(f"file:{abs_path}?mode=ro", uri=True)


def _validate_sql(sql: str) -> bool:
    stripped = sql.strip().upper()
    if not stripped:
        return False
    if not (
        stripped.startswith("SELECT")
        or stripped.startswith("WITH")
        or stripped.startswith("EXPLAIN")
    ):
        return False
    dangerous = [
        "DROP ", "DELETE ", "INSERT ", "UPDATE ", "ALTER ",
        "CREATE ", "ATTACH ", "DETACH ", "REINDEX ", "REPLACE ",
        "VACUUM ", "PRAGMA ",
    ]
    upper_sql = f" {stripped} "
    return not any(f" {kw}" in upper_sql for kw in dangerous)


def _execute_query(sql_query: str, db_path: str) -> pd.DataFrame:
    conn = _get_readonly_connection(db_path)
    try:
        return pd.read_sql_query(sql_query, conn)
    finally:
        conn.close()


def _format_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        cl = col.lower()
        if any(x in cl for x in ["amount", "avg", "sum", "total", "transaction"]):
            if df[col].dtype in ("int64", "float64"):
                df[col] = df[col].apply(_format_currency)
    return df


def _build_conversation_context() -> str:
    turns = st.session_state.conversation[-config.max_conversation_turns:]
    lines = []
    for t in turns:
        lines.append(f"User: {t['q']}")
        preview = t.get("insight_preview", "")
        if preview:
            lines.append(f"Answer: {preview}")
    return "\n".join(lines)


# ── Sidebar ──


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### \U0001f4dc Conversation")
        if st.session_state.conversation:
            for turn in st.session_state.conversation[-10:]:
                st.markdown(
                    f'<div class="conv-turn">'
                    f'<div class="conv-q">\U0001f4ac {turn["q"][:80]}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
            if st.button("\U0001f504 New Conversation"):
                st.session_state.conversation = []
                st.rerun()
        else:
            st.info("Ask a question to start the conversation.")

        st.divider()
        st.markdown("### \U0001f4dd Query History")
        if st.session_state.query_history:
            for i, entry in enumerate(reversed(st.session_state.query_history[-15:])):
                idx = len(st.session_state.query_history) - i
                q_text = entry.get("q", "")
                truncated = q_text[:50] + ("..." if len(q_text) > 50 else "")
                with st.container():
                    st.caption(f"#{idx}")
                    st.markdown(f"**Q:** {truncated}")
                    sql = entry.get("sql", "")
                    if sql:
                        st.code(sql, language="sql")
                    st.divider()
            if st.button("\U0001f5d1 Clear History"):
                st.session_state.query_history = []
                st.session_state.cache = {}
                st.rerun()
        else:
            st.info("No queries yet.")
        st.divider()
        st.caption(
            f"\u26a1 {config.rate_limit_per_minute} req/min  |  "
            f"{config.max_conversation_turns} context turns"
        )


# ── Main UI ──


def _render_header() -> None:
    st.markdown(
        '<div class="main-header">InsightX Analytics</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-header">AI-powered insights from your transaction data</div>',
        unsafe_allow_html=True,
    )


def _render_query_form() -> tuple[bool, str]:
    with st.form(key="query_form"):
        user_query = st.text_input(
            "Ask a question",
            placeholder="e.g., What is the failure rate for Android users on weekends?",
            max_chars=config.max_query_length,
            label_visibility="hidden",
        )
        submitted = st.form_submit_button("Generate Insights")
    return submitted, user_query


def _process_query(user_query: str) -> Optional[dict]:
    if not _check_rate_limit():
        st.error(
            f"Rate limit exceeded. Max {config.rate_limit_per_minute} queries per minute."
        )
        return None

    cache_key_val = _cache_key(user_query)
    cached = st.session_state.cache.get(cache_key_val)
    if cached is not None:
        st.success("Returning cached result from a previous identical query.")
        return cached

    status = st.status("Analyzing database...", expanded=True)

    try:
        status.write("Generating SQL from your question...")
        context = _build_conversation_context()
        raw = generate_sql_from_nvidia(user_query, conversation_context=context)
        sql_queries = extract_sql(raw)

        if not sql_queries or not sql_queries[0]:
            status.update(label="Failed to generate SQL", state="error")
            st.error(
                "The AI could not generate a valid SQL query. Try rephrasing."
            )
            return None

        status.write("Validating query safety...")
        for q in sql_queries:
            if not _validate_sql(q):
                status.update(label="Query rejected (safety)", state="error")
                st.error(
                    f"A generated query was rejected as potentially unsafe: "
                    f"`{q[:80]}`"
                )
                return None

        status.write("Executing query against database...")
        dfs: list[pd.DataFrame] = []
        for q in sql_queries:
            dfs.append(_execute_query(q, config.db_path))

        combined_df = (
            pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
        )

        status.write("Generating AI insight from results...")
        insight = generate_insight_from_data(
            user_query, combined_df.to_string(), conversation_context=context
        )

        status.update(label="Analysis complete!", state="complete")

        entry = {
            "q": user_query,
            "sql": sql_queries,
            "dfs": dfs,
            "df": combined_df,
            "insight": insight,
            "ts": time.time(),
        }
        st.session_state.cache[cache_key_val] = entry
        st.session_state.query_history.append(entry)
        st.session_state.conversation.append(
            {"q": user_query, "insight_preview": insight[:200]}
        )
        return entry

    except FileNotFoundError:
        status.update(label="Database not found", state="error")
        st.error(
            f"Database file '{config.db_path}' not found. "
            "Run `python data_engine.py` first to create it."
        )
        return None
    except sqlite3.OperationalError as e:
        status.update(label="SQL execution failed", state="error")
        st.error(f"Database error: {e}")
        return None
    except ValueError as e:
        status.update(label="Configuration error", state="error")
        st.error(str(e))
        return None
    except Exception as e:
        status.update(label="Analysis failed", state="error")
        st.error(f"An unexpected error occurred: {e}")
        logger.exception("Query processing failed")
        return None


def _render_results(result: dict) -> None:
    insight = result["insight"].replace("$", "\u20b9")
    sql_queries: list[str] = result.get("sql", [])
    dfs: list[pd.DataFrame] = result.get("dfs", [result["df"]])
    combined_df = result["df"]

    st.divider()

    tab1, tab2, tab3 = st.tabs(
        ["\U0001f4cb AI Insight", "\U0001f4ca Results", "\U0001f50d Generated SQL"]
    )

    with tab1:
        st.markdown(insight)

    with tab2:
        if combined_df.empty:
            st.warning("No records matched your criteria.")
        else:
            if len(dfs) > 1:
                for i, (q, df_part) in enumerate(zip(sql_queries, dfs)):
                    with st.expander(f"Query {i+1}: {q[:60]}..."):
                        formatted = _format_dataframe(df_part)
                        st.dataframe(
                            formatted, use_container_width=True, hide_index=True
                        )
            else:
                formatted = _format_dataframe(combined_df)
                st.dataframe(
                    formatted, use_container_width=True, hide_index=True
                )

            csv_data = StringIO()
            combined_df.to_csv(csv_data, index=False)
            st.download_button(
                label="\U0001f4e5 Download CSV",
                data=csv_data.getvalue(),
                file_name=f"insightx_export_{int(time.time())}.csv",
                mime="text/csv",
            )

    with tab3:
        for i, q in enumerate(sql_queries):
            if len(sql_queries) > 1:
                st.markdown(f"**Query {i+1}**")
            st.code(q, language="sql")

    components.html(
        "<script>window.parent.document.querySelector('.stStatus')?.scrollIntoView({behavior: 'smooth'});</script>",
        height=0,
    )


def _render_database_ledger() -> None:
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("\U0001f4c2 View Full Database Ledger"):
        try:
            conn = _get_readonly_connection(config.db_path)
            full_df = pd.read_sql_query(
                "SELECT * FROM transactions LIMIT 100", conn
            )
            conn.close()
            if "transaction_amount" in full_df.columns:
                full_df["transaction_amount"] = full_df[
                    "transaction_amount"
                ].map("\u20b9{:,.2f}".format)
            st.dataframe(full_df, use_container_width=True, hide_index=True)
            st.caption(f"Showing up to 100 rows from {config.db_path}")
        except FileNotFoundError:
            st.error(
                f"Database '{config.db_path}' not found. "
                "Run `python data_engine.py` first."
            )
        except Exception as e:
            st.error(f"Could not load database: {e}")
            logger.exception("Failed to load ledger")


# ── Entry Point ──

_render_sidebar()
_render_header()

submitted, user_query = _render_query_form()

if submitted and user_query and user_query.strip():
    result = _process_query(user_query.strip())
    if result is not None:
        _render_results(result)

_render_database_ledger()
