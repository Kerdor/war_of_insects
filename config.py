import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class AccountConfig:
    phone: str
    session_name: str


def load_accounts() -> list[AccountConfig]:
    accounts = []
    for index in range(1, 4):
        phone = os.getenv(f"PHONE_{index}", "").strip()
        session_name = os.getenv(f"SESSION_NAME_{index}", "").strip()
        if phone and session_name:
            accounts.append(AccountConfig(phone=phone, session_name=session_name))
    return accounts


API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "War_of_Insects")
ACCOUNTS = load_accounts()
