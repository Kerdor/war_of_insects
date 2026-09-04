import asyncio

from agent import Agent
from config import ACCOUNTS
from telegram_client import GameClient


async def main():
    enabled_accounts = [account for account in ACCOUNTS if account.enabled]

    if not enabled_accounts:
        raise RuntimeError("No enabled accounts configured. Set ACCOUNT_N_ENABLED=true in .env")

    print(f"Configured enabled accounts: {len(enabled_accounts)}")
    for account in enabled_accounts:
        print(f"Enabled: {account.session_name}")

    agent = Agent()
    clients = []

    try:
        for account in enabled_accounts:
            client = GameClient(account)
            print(f"Connecting: {account.session_name}")
            await client.connect()
            print(f"Connected: {account.session_name}")
            clients.append((account, client))

        async def play(account, client):
            try:
                while True:
                    message = await client.get_latest()
                    if message is not None:
                        try:
                            await agent.step(client, message, account.session_name)
                        except Exception as error:
                            print(f"[{account.session_name}] Agent error: {error}")
                    await asyncio.sleep(1.0)
            finally:
                await client.disconnect()

        await asyncio.gather(*(play(account, client) for account, client in clients))
    finally:
        for _, client in clients:
            if client.is_connected():
                await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
