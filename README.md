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
User Question → NVIDIA NIM LLM → SQL Query → SQLite DB → Results → NVIDIA NIM LLM → Structured Insight
                       ↑                                                          ↑
                  System Prompt                                            Data-Grounded Prompt
```

The second pass only ever sees the rows the database actually returned, so an
insight cannot claim a number that was not in the result set.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.8+ |
| Web UI | Streamlit |
| AI / LLM | NVIDIA NIM via its OpenAI-compatible API (`openai` client), `minimaxai/minimax-m3` by default |
| Database | SQLite |
| Data Processing | Pandas |
| Configuration | `python-dotenv` + `config.py` |

## Project Structure

```
InsightX/
├── app.py                    # Streamlit web UI (main entry point)
├── main_app.py               # CLI version (alternative entry point)
├── config.py                 # Central configuration from environment
├── data_engine.py            # CSV → clean → SQLite pipeline
├── seed_data.py              # Generates the synthetic 5,000-row dataset
├── text_to_sql_engine.py     # NVIDIA NIM integration: SQL gen + insight gen
├── tests/                    # Pytest suite
├── start.bat                 # Windows launcher
├── requirements.txt          # Runtime dependencies
├── requirements-dev.txt      # Test and lint dependencies
├── README.md                 # This file
├── .env.example              # Template for .env
├── transactions.db           # SQLite database (generated, gitignored)
└── insightx_transactions.csv # Source dataset (generated, gitignored)
```

## Prerequisites

- Python 3.8+
- [NVIDIA NIM API key](https://build.nvidia.com/) — the engine talks to
  NVIDIA's OpenAI-compatible endpoint

## Setup

```bash
# 1. Clone the repository
cd InsightX

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
# Edit .env and set your NVIDIA_API_KEY

# 5. Generate the dataset and build the database
python seed_data.py     # writes insightx_transactions.csv (5,000 rows)
python data_engine.py   # writes transactions.db

# 6. Launch the app
streamlit run app.py
```

On Windows, `start.bat` does steps 5 and 6 for you.

The app opens at `http://localhost:8501`.

### About the data

`seed_data.py` generates a synthetic dataset of 5,000 payment transactions
across 2025 — P2P and P2M transfers, ten merchant categories, ten banks, ten
states, a weighted success/failure/pending split, and a 3 % fraud flag. It is
seeded with `random.seed(42)`, so the dataset is identical on every machine.

Because the data is synthetic, the app is a demonstration of the query engine
rather than an analysis of real payment traffic. Point `CSV_PATH` at a real
export with the same column names to run it on real data.

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

## Tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

The suite covers the data pipeline (seed reproducibility, cleaning, derived
columns, database creation), the SQL parser (markdown fences, the `SQL:`
label, the `;--Q--;` multi-query delimiter) and the safety layer — that
`SELECT`, `WITH` and `EXPLAIN` are accepted while `DROP`, `DELETE`, `INSERT`,
`UPDATE`, `ALTER`, `CREATE`, `ATTACH`, `PRAGMA`, `VACUUM` and `REINDEX` are
rejected, and that the read-only connection actually refuses writes.

No API key is needed: the tests generate their own dataset and never call the
LLM.

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Harshit Shyamsukha.
