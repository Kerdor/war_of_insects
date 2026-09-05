import asyncio

from .telegram_client import GameClient


class Agent:
    """Minimal agent shell for the new self-learning architecture."""

    async def run(self, client: GameClient, account_id: str) -> None:
        while True:
            message = await client.get_latest()
            if message is not None:
                text = (message.text or "").strip()
                if text:
                    print(f"[{account_id}] {text[:500]}")
            await asyncio.sleep(1.0)
