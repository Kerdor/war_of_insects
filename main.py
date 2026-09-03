import asyncio

from agent import Agent
from config import ACCOUNTS
from telegram_client import GameClient


async def run_account(account):
    client = GameClient(account)
    agent = Agent()

    await client.connect()
    print(f"Connected: {account.session_name}")

    try:
        while True:
            message = await client.get_latest()
            if message is not None:
                try:
                    await agent.step(client, message)
                except Exception as error:
                    print(f"[{account.session_name}] Agent error: {error}")
            await asyncio.sleep(1.0)
    finally:
        await client.disconnect()


async def main():
    if not ACCOUNTS:
        raise RuntimeError("No accounts configured. Set PHONE_N and SESSION_NAME_N in .env")

    tasks = [asyncio.create_task(run_account(account)) for account in ACCOUNTS]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
