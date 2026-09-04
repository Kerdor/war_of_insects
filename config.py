import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class AccountConfig:
    phone: str
    session_name: str
    enabled: bool


def load_accounts() -> list[AccountConfig]:
    accounts = []
    for index in range(1, 4):
        phone = os.getenv(f"PHONE_{index}", "").strip()
        session_name = os.getenv(f"SESSION_NAME_{index}", "").strip()
        enabled = os.getenv(f"ACCOUNT_{index}_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
        if phone and session_name:
            accounts.append(AccountConfig(phone=phone, session_name=session_name, enabled=enabled))
    return accounts


API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "War_of_Insects")
QWEN_ENABLED = os.getenv("QWEN_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "").strip()
QWEN_BASE_URL = os.getenv(
    "QWEN_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
).strip().rstrip("/")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus").strip()
QWEN_ANALYSIS_INTERVAL = max(1, int(os.getenv("QWEN_ANALYSIS_INTERVAL", "10")))
QWEN_MAX_TOKENS = max(256, int(os.getenv("QWEN_MAX_TOKENS", "1200")))
QWEN_TIMEOUT = max(5, int(os.getenv("QWEN_TIMEOUT", "30")))
ACCOUNTS = load_accounts()
