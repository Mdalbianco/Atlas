import asyncio
import os

from dotenv import load_dotenv
from telegram import Bot


class NotificationService:
    """Invia notifiche Telegram."""

    def __init__(self) -> None:
        load_dotenv()

        self.token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

    async def send(self, message: str) -> bool:
        """Invia un messaggio Telegram."""

        if not self.token or not self.chat_id:
            return False

        async with Bot(token=self.token) as bot:
            await bot.send_message(
                chat_id=self.chat_id,
                text=message,
            )

        return True

    def send_sync(self, message: str) -> bool:
        """Invia un messaggio Telegram da codice sincrono."""

        return asyncio.run(self.send(message))