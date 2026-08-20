# InsightX Analytics

AI-powered Text-to-SQL engine for digital payment transaction analysis. Ask questions in plain English and get structured, fact-based business insights grounded in real database results.

## Features

- **Natural Language Querying** — Ask questions like *"What is the failure rate for Android users on weekends?"* and get instant answers.
- **Two-Pass AI Architecture** — Gemini generates SQL → executes against real DB → second pass produces insights *strictly* from returned data, preventing hallucination.
- **Structured Business Insights** — Every response includes Direct Response, Supporting Statistics, Contextual Insights, and a Recommendation.
- **Smart Formatting** — Monetary values auto-formatted to Indian Rupees (₹) across UI and AI responses.
- **Query History** — Sidebar tracks recent queries with generated SQL for reference.
- **Query Caching** — Identical queries return cached results within a configurable TTL.
- **Rate Limiting** — Configurable requests-per-minute to protect API quota.
- **Results Export** — Download any result set as CSV.
- **SQL Safety** — Read-only database connection + SQL validation blocks dangerous operations.
- **Dark/Light Mode** — Automatically adapts to system theme.
- **Modern UI** — Clean typography (Inter), gradient buttons, responsive layout.

## Architecture

```
User Question → Gemini LLM → SQL Query → SQLite DB → Results → Gemini LLM → Structured Insight
                      ↑                                                        ↑
                 System Prompt                                            Data-Grounded Prompt
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.8+ |
| Web UI | Streamlit |
| AI / LLM | Google Gemini 2.5 Flash (via `google-genai` SDK) |
| Database | SQLite |
| Data Processing | Pandas |
| Configuration | `python-dotenv` + `config.py` |

## Project Structure

```
InsightX-proj/
├── app.py                    # Streamlit web UI (main entry point)
├── config.py                 # Central configuration from environment
├── data_engine.py            # CSV → clean → SQLite pipeline
├── text_to_sql_engine.py     # Gemini integration: SQL gen + insight gen
├── main_app.py               # CLI version (alternative entry point)
├── .env                      # API key and configuration (not committed)
├── .env.example              # Template for .env
├── requirements.txt          # Python dependencies
├── transactions.db           # SQLite database (generated)
├── insightx_transactions.csv # Source dataset
└── "InsightX Readme.md"      # This file
```

## Prerequisites

- Python 3.8+
- [Google Gemini API key](https://ai.google.dev/)

## Setup

```bash
# 1. Clone the repository
cd InsightX-proj

# 2. Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API key
copy .env.example .env
# Edit .env and set your GEMINI_API_KEY

# 5. Build the database (optional — transactions.db may be included)
python data_engine.py

# 6. Launch the app
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Configuration

All settings are controlled via environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `NVIDIA_API_KEY` | — | **Required.** NVIDIA NIM API key |
| `NVIDIA_API_BASE` | `https://integrate.api.nvidia.com/v1` | NVIDIA NIM endpoint |
| `NVIDIA_MODEL` | `minimaxai/minimax-m3` | Model name on NVIDIA NIM |
| `DB_PATH` | `transactions.db` | SQLite database file path |
| `CSV_PATH` | `insightx_transactions.csv` | Source CSV for data pipeline |
| `MAX_QUERY_LENGTH` | `500` | Max characters for user input |
| `MAX_RESULTS_SHOWN` | `1000` | Max rows displayed in results |
| `RATE_LIMIT_PER_MINUTE` | `30` | Max queries per minute |
| `CACHE_TTL_SECONDS` | `600` | How long to cache query results |
| `MAX_CONVERSATION_TURNS` | `5` | Turns of context for follow-ups |

## CLI Usage

```bash
python main_app.py
```

This runs the same engine in the terminal for scripting or testing.

## CLI Usage (alternate)

```bash
python data_engine.py
```

Regenerates `transactions.db` from the source CSV and runs ground-truth verification.

## Safety

- **Read-only database connection** — The app connects with `mode=ro`, making all destructive SQL impossible at the engine level.
- **SQL validation** — Before execution, queries are checked for `SELECT`/`WITH`/`EXPLAIN` compliance and scanned for dangerous keywords.
- **Input limits** — User input is capped by `MAX_QUERY_LENGTH`.
- **Rate limiting** — Configurable sliding-window rate limiter prevents API abuse.
