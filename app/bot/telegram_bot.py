import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.utils.logger import log


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Risponde al comando /start."""

    if update.message is None:
        return

    await update.message.reply_text(
        "🚀 Ciao!\n\n"
        "Sono Atlas.\n"
        "Il sistema Telegram è operativo."
    )


def create_telegram_application() -> Application:
    """Crea e configura l'applicazione Telegram."""

    load_dotenv()

    token = os.getenv("TELEGRAM_TOKEN")

    if not token:
        raise ValueError(
            "TELEGRAM_TOKEN non trovato. Controlla il file .env."
        )

    application = Application.builder().token(token).build()

    application.add_handler(
        CommandHandler("start", start_command)
    )

    return application


def run_telegram_bot() -> None:
    """Avvia il bot Telegram in modalità polling."""

    application = create_telegram_application()

    log("Telegram collegato")
    log("Bot in ascolto. Premi Ctrl+C per arrestarlo.")

    application.run_polling()