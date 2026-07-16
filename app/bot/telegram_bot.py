import os

import ccxt
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from app.exchange.exchange_manager import ExchangeManager
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
        "Il sistema Telegram è operativo.\n\n"
        "Comandi disponibili:\n"
        "/start - Avvia Atlas\n"
        "/saldo - Mostra il saldo Kraken"
        "/prezzo - Mostra il prezzo BTC/EUR"
    )


async def balance_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Mostra il saldo dell'account Kraken."""

    if update.message is None:
        return

    await update.message.reply_text(
        "⏳ Sto leggendo il saldo Kraken..."
    )

    try:
        exchange_manager = ExchangeManager()
        balances = exchange_manager.get_non_zero_balances()

        if not balances:
            message = (
                "💰 Saldo Kraken\n\n"
                "Connessione: ✅\n"
                "Nessun fondo presente sul conto."
            )
        else:
            lines = [
                "💰 Saldo Kraken",
                "",
                "Connessione: ✅",
                "",
            ]

            for currency, amount in sorted(balances.items()):
                lines.append(f"{currency}: {amount}")

            message = "\n".join(lines)

        await update.message.reply_text(message)
        log("Saldo Kraken inviato tramite Telegram")

    except ccxt.AuthenticationError:
        log("Errore di autenticazione Kraken")

        await update.message.reply_text(
            "❌ Autenticazione Kraken non riuscita.\n"
            "Controlla API Key, Secret e permessi."
        )

    except ccxt.NetworkError:
        log("Errore di rete durante la connessione a Kraken")

        await update.message.reply_text(
            "❌ Kraken non è raggiungibile in questo momento.\n"
            "Riprova tra poco."
        )

    except ccxt.ExchangeError as error:
        log(f"Errore Kraken: {error}")

        await update.message.reply_text(
            "❌ Kraken ha restituito un errore."
        )

    except Exception as error:
        log(f"Errore imprevisto nel comando /saldo: {error}")

        await update.message.reply_text(
            "❌ Si è verificato un errore imprevisto."
        )
async def price_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Mostra il prezzo attuale di BTC/EUR."""

    if update.message is None:
        return

    await update.message.reply_text(
        "⏳ Sto leggendo il prezzo di BTC/EUR..."
    )

    try:
        exchange_manager = ExchangeManager()

        market_data = exchange_manager.get_market_price("BTC/EUR")

        last_price = market_data.get("last")
        bid_price = market_data.get("bid")
        ask_price = market_data.get("ask")
        high_price = market_data.get("high")
        low_price = market_data.get("low")
        percentage = market_data.get("percentage")

        percentage_text = (
            f"{percentage:.2f}%"
            if percentage is not None
            else "Non disponibile"
        )

        message = (
            "📈 BTC/EUR\n\n"
            f"Ultimo prezzo: {last_price} €\n"
            f"Acquisto bid: {bid_price} €\n"
            f"Vendita ask: {ask_price} €\n"
            f"Massimo 24h: {high_price} €\n"
            f"Minimo 24h: {low_price} €\n"
            f"Variazione 24h: {percentage_text}"
        )

        await update.message.reply_text(message)

        log("Prezzo BTC/EUR inviato tramite Telegram")

    except ccxt.NetworkError:
        log("Errore di rete durante la lettura del prezzo")

        await update.message.reply_text(
            "❌ Kraken non è raggiungibile in questo momento."
        )

    except ccxt.ExchangeError as error:
        log(f"Errore Kraken durante la lettura del prezzo: {error}")

        await update.message.reply_text(
            "❌ Kraken ha restituito un errore."
        )

    except Exception as error:
        log(f"Errore imprevisto nel comando /prezzo: {error}")

        await update.message.reply_text(
            "❌ Si è verificato un errore imprevisto."
        )

def create_telegram_application() -> Application:
    """Crea e configura l'applicazione Telegram."""

    load_dotenv()

    token = os.getenv("TELEGRAM_TOKEN")

    if not token:
        raise ValueError(
            "TELEGRAM_TOKEN non trovato. "
            "Controlla il file .env."
        )

    application = Application.builder().token(token).build()

    application.add_handler(
        CommandHandler("start", start_command)
    )

    application.add_handler(
        CommandHandler("saldo", balance_command)
    )

    application.add_handler(
    CommandHandler("prezzo", price_command)
    )
    return application


def run_telegram_bot() -> None:
    """Avvia il bot Telegram in modalità polling."""

    application = create_telegram_application()

    log("Telegram collegato")
    log("Bot in ascolto. Arresta il terminale per fermarlo.")

    application.run_polling()