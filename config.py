import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
    nvidia_api_base: str = os.getenv(
        "NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1"
    )
    nvidia_model: str = os.getenv("NVIDIA_MODEL", "minimaxai/minimax-m3")
    db_path: str = os.getenv("DB_PATH", "transactions.db")
    csv_path: str = os.getenv("CSV_PATH", "insightx_transactions.csv")
    max_query_length: int = int(os.getenv("MAX_QUERY_LENGTH", "500"))
    max_results_shown: int = int(os.getenv("MAX_RESULTS_SHOWN", "1000"))
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "600"))
    max_conversation_turns: int = int(
        os.getenv("MAX_CONVERSATION_TURNS", "5")
    )


config = Config()
