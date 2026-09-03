from telethon import TelegramClient

from config import API_HASH, API_ID, BOT_USERNAME, AccountConfig


class GameClient:
    def __init__(self, account: AccountConfig):
        self.account = account
        self.client = TelegramClient(account.session_name, API_ID, API_HASH)

    async def connect(self) -> None:
        await self.client.start(phone=self.account.phone)

    async def disconnect(self) -> None:
        await self.client.disconnect()

    async def send(self, text: str):
        return await self.client.send_message(BOT_USERNAME, text)

    async def get_latest(self):
        messages = await self.client.get_messages(BOT_USERNAME, limit=1)
        return messages[0] if messages else None
