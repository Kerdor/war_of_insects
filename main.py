import asyncio

from bot.agent import Agent
from config import ACCOUNTS
from bot.telegram_client import GameClient


async def main():
    enabled_accounts = [account for account in ACCOUNTS if account.enabled]

    if not enabled_accounts:
        raise RuntimeError("No enabled accounts configured. Set ACCOUNT_N_ENABLED=true in .env")

    print(f"Configured enabled accounts: {len(enabled_accounts)}")

    clients = []
    try:
        for account in enabled_accounts:
            client = GameClient(account)
            print(f"Connecting: {account.session_name}")
            await client.connect()
            print(f"Connected: {account.session_name}")
            clients.append((account, client))

        agent = Agent()
        await asyncio.gather(*(agent.run(client, account.session_name) for account, client in clients))
    finally:
        for _, client in clients:
            if client.client.is_connected():
                await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
