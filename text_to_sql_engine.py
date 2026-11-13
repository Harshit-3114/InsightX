import logging
import re
import time

from openai import OpenAI

from config import config

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
You are an expert Data Analyst and SQL Developer for a digital payments company.

DATABASE SCHEMA:
Table Name: transactions
Columns:
-transaction_id (TEXT)
-timestamp (TEXT)
-transaction_type (TEXT)
-merchant_category (TEXT)
-transaction_amount (INTEGER)
-transaction_status (TEXT)
-sender_age_group (TEXT)
-receiver_age_group (TEXT)
-sender_state (TEXT)
-sender_bank (TEXT)
-receiver_bank (TEXT)
-device_type (TEXT)
-network_type (TEXT)
-fraud_flag (INTEGER)
-hour_of_day (INTEGER)
-day_of_week (TEXT)
-is_weekend (INTEGER)
-time_block (TEXT)
-is_high_value (INTEGER)

BUSINESS RULES:
1. Failure Rate = (SUM(CASE WHEN transaction_status = 'FAILED' THEN 1 ELSE 0 END) * 100.0) / COUNT(*)
2. High Value = transaction_amount >= 5000
3. Always use exact string matches like 'Android', 'FAILED'

CONVERSATION CONTEXT:
- If the user asks a follow-up question (e.g., "What about iOS?"), use the conversation history above
  to understand what they are referring to.
- If the user asks multiple distinct questions in one message, generate a separate SQL query for each one.

MULTI-QUERY FORMAT (if needed):
- Separate multiple SQL queries with the exact delimiter: ;--Q--;
- Each query will be executed independently against the database.

OUTPUT FORMAT (STRICTLY FOLLOW THIS FORMAT):
SQL:
<Write the raw SQL query without markdown blocks>
"""


def _get_client() -> OpenAI:
    if not config.nvidia_api_key:
        raise ValueError(
            "NVIDIA_API_KEY not found. Create a .env file with your API key. "
            "See .env.example for reference."
        )
    return OpenAI(api_key=config.nvidia_api_key, base_url=config.nvidia_api_base)


def _call_llm(
    system_prompt: str,
    user_content: str,
    max_retries: int = 2,
) -> str:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            client = _get_client()
            response = client.chat.completions.create(
                model=config.nvidia_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.0,
            )
            text = response.choices[0].message.content
            if text is None:
                raise ValueError("Model returned an empty response")
            return text
        except Exception as e:
            last_error = e
            logger.warning(
                "Attempt %d/%d failed: %s", attempt + 1, max_retries + 1, e
            )
            if attempt < max_retries:
                time.sleep(1)

    raise RuntimeError("LLM call failed after retries") from last_error


def generate_sql_from_nvidia(
    user_query: str,
    conversation_context: str = "",
    max_retries: int = 2,
) -> str:
    logger.info("Generating SQL for query: '%s'", user_query[:80])

    contents = user_query
    if conversation_context:
        contents = (
            f"Conversation history:\n{conversation_context.strip()}"
            f"\n\nCurrent question: {user_query}"
        )

    return _call_llm(SYSTEM_PROMPT, contents, max_retries)


def extract_sql(response_text: str) -> list[str]:
    if not response_text:
        return [""]

    cleaned = (
        response_text.replace("```sql", "")
        .replace("```sqlite", "")
        .replace("```", "")
        .strip()
    )

    if cleaned.upper().startswith("SQL"):
        cleaned = cleaned[3:].strip()
    if cleaned.startswith(":"):
        cleaned = cleaned[1:].strip()

    parts = re.split(r";--Q--;", cleaned)
    queries = []
    for part in parts:
        part = part.strip().rstrip(";").strip()
        if part:
            queries.append(part)

    return queries if queries else [""]


INSIGHT_PROMPT_TEMPLATE = """
The user asked: "{user_query}"
{context_block}
Database returned:
{db_results}

TASK:
    Analyze the database result and provide a highly structured, professional insight.
    You MUST format your response exactly using the four bullet points below.

    * **Direct Response:** [Answer in one sentence]
    * **Supporting Statistics:** [Cite exact metrics from the database result]
    * **Contextual Insights:** [Explain the business pattern or trend]
    * **Recommendation:** [Provide a logical, actionable next step]

    STRICT CONSTRAINTS:
    - Use \u20b9 for monetary values.
    - Base statistics ONLY on the provided data.
"""


def generate_insight_from_data(
    user_query: str,
    db_results: str,
    conversation_context: str = "",
    max_retries: int = 2,
) -> str:
    context_block = (
        f"Conversation context: {conversation_context.strip()}"
        if conversation_context
        else ""
    )
    prompt = INSIGHT_PROMPT_TEMPLATE.format(
        user_query=user_query,
        context_block=context_block,
        db_results=db_results,
    )
    return _call_llm("You are a helpful data analyst.", prompt, max_retries)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s: %(message)s"
    )
    print("Testing NVIDIA NIM connection...")
    test_query = "What is the failure rate for Android users on Weekends?"
    try:
        raw = generate_sql_from_nvidia(test_query)
        queries = extract_sql(raw)
        print("\nGenerated SQL:")
        for q in queries:
            print(q)
    except Exception as e:
        print(f"Error: {e}")
