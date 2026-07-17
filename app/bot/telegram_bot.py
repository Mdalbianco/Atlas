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
from app.services.watchlist_service import WatchlistService
from app.analysis.analysis_manager import AnalysisManager
from app.analysis.report import AnalysisReport
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
    "/start - Mostra i comandi\n"
    "/saldo - Mostra il saldo Kraken\n"
    "/prezzo BTC - Mostra il prezzo in EUR\n"
    "/watch - Mostra la watchlist\n"
    "/watch add BTC - Aggiunge una crypto\n"
    "/watch remove BTC - Rimuove una crypto"
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
    """Mostra il prezzo della criptovaluta richiesta contro EUR."""

    if update.message is None:
        return

    if not context.args:
        await update.message.reply_text(
            "ℹ️ Specifica una criptovaluta.\n\n"
            "Esempi:\n"
            "/prezzo BTC\n"
            "/prezzo ETH\n"
            "/prezzo SOL"
        )
        return

    base_currency = context.args[0].upper()
    symbol = f"{base_currency}/EUR"

    await update.message.reply_text(
        f"⏳ Sto leggendo il prezzo di {symbol}..."
    )

    try:
        exchange_manager = ExchangeManager()
        market_data = exchange_manager.get_market_price(symbol)

        last_price = market_data.get("last")
        bid_price = market_data.get("bid")
        ask_price = market_data.get("ask")
        high_price = market_data.get("high")
        low_price = market_data.get("low")
        percentage = market_data.get("percentage")

        def format_price(value: float | None) -> str:
            if value is None:
                return "Non disponibile"

            return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace(
                "X", "."
            )

        percentage_text = (
            f"{percentage:+.2f}%"
            if percentage is not None
            else "Non disponibile"
        )

        message = (
            f"📈 {symbol}\n\n"
            f"Ultimo prezzo: {format_price(last_price)} €\n"
            f"Bid: {format_price(bid_price)} €\n"
            f"Ask: {format_price(ask_price)} €\n"
            f"Massimo 24h: {format_price(high_price)} €\n"
            f"Minimo 24h: {format_price(low_price)} €\n"
            f"Variazione 24h: {percentage_text}"
        )

        await update.message.reply_text(message)
        log(f"Prezzo {symbol} inviato tramite Telegram")

    except ccxt.BadSymbol:
        log(f"Coppia non disponibile su Kraken: {symbol}")

        await update.message.reply_text(
            f"❌ La coppia {symbol} non è disponibile su Kraken."
        )

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
async def analysis_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Esegue l'analisi completa di una criptovaluta."""

    if update.message is None:
        return

    if not context.args:
        await update.message.reply_text(
            "📊 Specifica una criptovaluta.\n\n"
            "Esempi:\n"
            "/analizza BTC\n"
            "/analizza ETH\n"
            "/analizza SOL"
        )
        return

    symbol = context.args[0].upper()

    await update.message.reply_text(
        f"🧠 Atlas sta analizzando {symbol}..."
    )

    try:
        analysis_manager = AnalysisManager()
        report_generator = AnalysisReport()

        result = analysis_manager.analyze(symbol)
        report = report_generator.generate(result)

        await update.message.reply_text(report)

        log(f"Analisi inviata per {symbol}")

    except Exception as error:
        log(f"Errore durante l'analisi: {error}")

        await update.message.reply_text(
            "❌ Errore durante l'analisi della criptovaluta."
        )
async def watch_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Mostra, aggiunge o rimuove crypto dalla watchlist."""

    if update.message is None:
        return

    watchlist = WatchlistService()

    # Comando senza argomenti: /watch
    if not context.args:
        symbols = watchlist.get_symbols()

        if not symbols:
            message = (
                "👀 Watchlist Atlas\n\n"
                "La watchlist è vuota.\n\n"
                "Aggiungi una crypto con:\n"
                "/watch add BTC"
            )
        else:
            symbol_lines = [
                f"• {symbol}/EUR"
                for symbol in symbols
            ]

            message = (
                "👀 Watchlist Atlas\n\n"
                + "\n".join(symbol_lines)
                + "\n\n"
                "Comandi:\n"
                "/watch add BTC\n"
                "/watch remove BTC"
            )

        await update.message.reply_text(message)
        return

    action = context.args[0].lower()

    # Controlla che sia stata indicata anche una crypto
    if len(context.args) < 2:
        await update.message.reply_text(
            "ℹ️ Devi specificare una criptovaluta.\n\n"
            "Esempi:\n"
            "/watch add BTC\n"
            "/watch remove BTC"
        )
        return

    symbol = context.args[1].upper()

    # Accettiamo soltanto simboli semplici come BTC, ETH o SOL
    if not symbol.isalnum() or len(symbol) > 15:
        await update.message.reply_text(
            "❌ Simbolo non valido.\n\n"
            "Esempio corretto: /watch add BTC"
        )
        return

    if action == "add":
        added = watchlist.add_symbol(symbol)

        if added:
            await update.message.reply_text(
                f"✅ {symbol} aggiunto alla watchlist."
            )
            log(f"{symbol} aggiunto alla watchlist")
        else:
            await update.message.reply_text(
                f"ℹ️ {symbol} è già presente nella watchlist."
            )

        return

    if action == "remove":
        removed = watchlist.remove_symbol(symbol)

        if removed:
            await update.message.reply_text(
                f"🗑️ {symbol} rimosso dalla watchlist."
            )
            log(f"{symbol} rimosso dalla watchlist")
        else:
            await update.message.reply_text(
                f"ℹ️ {symbol} non è presente nella watchlist."
            )

        return

    await update.message.reply_text(
        "❌ Azione non riconosciuta.\n\n"
        "Comandi disponibili:\n"
        "/watch\n"
        "/watch add BTC\n"
        "/watch remove BTC"
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

    application.add_handler(
    CommandHandler("analizza", analysis_command)
    )
    
    application.add_handler(
    CommandHandler("watch", watch_command)
    )
    return application

def run_telegram_bot() -> None:
    """Avvia il bot Telegram in modalità polling."""

    application = create_telegram_application()

    log("Telegram collegato")
    log("Bot in ascolto. Arresta il terminale per fermarlo.")

    application.run_polling()