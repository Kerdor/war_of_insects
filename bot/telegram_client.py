from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import ReplyKeyboardMarkup

from config import API_HASH, API_ID, BOT_USERNAME, AccountConfig


class GameClient:
    def __init__(self, account: AccountConfig):
        self.account = account
        self.client = TelegramClient(account.session_name, API_ID, API_HASH)

    async def connect(self) -> None:
        await self.client.connect()

        if await self.client.is_user_authorized():
            print(f"Authorized session: {self.account.session_name}")
            return

        print(f"Requesting login code: {self.account.session_name}")
        sent_code = await self.client.send_code_request(self.account.phone)
        print(f"Login code requested: {self.account.session_name}")

        code = input(f"Enter Telegram code for {self.account.session_name}: ").strip()
        try:
            await self.client.sign_in(
                phone=self.account.phone,
                code=code,
                phone_code_hash=sent_code.phone_code_hash,
            )
        except SessionPasswordNeededError:
            password = input(f"Enter Telegram 2FA password for {self.account.session_name}: ")
            await self.client.sign_in(password=password)

    async def disconnect(self) -> None:
        await self.client.disconnect()

    async def send(self, text: str):
        return await self.client.send_message(BOT_USERNAME, text)

    async def get_latest(self):
        messages = await self.client.get_messages(BOT_USERNAME, limit=20)
        if not messages:
            return None

        for message in messages:
            if message.buttons:
                return message

        return messages[0]

    async def get_reply_keyboard_message(self):
        messages = await self.client.get_messages(BOT_USERNAME, limit=20)
        for message in messages:
            if isinstance(getattr(message, "reply_markup", None), ReplyKeyboardMarkup):
                return message
        return None

    async def get_current_buttons(self, message):
        buttons = []
        for row in message.buttons or []:
            buttons.extend(row)

        reply_message = await self.get_reply_keyboard_message()
        if reply_message is not None and reply_message.id != message.id:
            for row in reply_message.buttons or []:
                buttons.append(row)

        return buttons
