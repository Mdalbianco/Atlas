import os
import asyncio

from dotenv import load_dotenv
from telegram import Bot


class NotificationService:
    """Invia notifiche Telegram."""

    def __init__(self) -> None:
        load_dotenv()

        self.token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if self.token:
            self.bot = Bot(token=self.token)
        else:
            self.bot = None


    async def send(self, message: str) -> bool:
        """Invia un messaggio Telegram."""

        if self.bot is None:
            return False

        if not self.chat_id:
            return False

        await self.bot.send_message(
            chat_id=self.chat_id,
            text=message,
        )

        return True
    
    def send_sync(self, message: str) -> bool:
     """Invia un messaggio Telegram da codice sincrono."""

     return asyncio.run(self.send(message))