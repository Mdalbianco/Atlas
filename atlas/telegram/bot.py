"""Bot Telegram interattivo (python-telegram-bot v21+).

Controllo accessi:
- solo gli ID in ``TELEGRAM_ALLOWED_USERS`` (più gli admin) possono usare il bot;
- i comandi di controllo richiedono un ID in ``TELEGRAM_ADMIN_USERS``;
- se nessun utente è configurato il bot rifiuta TUTTI i comandi (fail-closed);
- i tentativi non autorizzati vengono registrati (solo l'ID numerico).
I comandi lenti (rete) girano in un thread per non bloccare il bot.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from atlas.app import Atlas
from atlas.logging_setup import get_logger

log = get_logger(__name__)

ADMIN_COMMANDS = {"pausa", "riprendi", "chiudi", "config", "modalita"}


class AccessControl:
    def __init__(self, allowed: frozenset[int], admins: frozenset[int]) -> None:
        self.admins = frozenset(admins)
        self.allowed = frozenset(allowed) | self.admins

    def can_use(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.allowed

    def is_admin(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.admins


class CommandRouter:
    """Logica dei comandi indipendente dalla libreria Telegram (testabile)."""

    def __init__(self, atlas: Atlas, access: AccessControl) -> None:
        self.atlas = atlas
        self.access = access
        a = atlas
        self.commands: dict[str, Callable[[list[str], bool], str]] = {
            "start": lambda args, adm: a.text_help(),
            "help": lambda args, adm: a.text_help(),
            "status": lambda args, adm: a.text_status(),
            "saldo": lambda args, adm: a.text_balance(),
            "prezzo": lambda args, adm: a.text_price(args[0]) if args else "Uso: /prezzo BTC",
            "watchlist": lambda args, adm: a.text_watchlist(args, adm),
            "analisi": lambda args, adm: a.text_analysis(args[0]) if args else "Uso: /analisi BTC",
            "segnali": lambda args, adm: a.text_signals(),
            "mercato": lambda args, adm: a.text_market(),
            "strategie": lambda args, adm: a.text_strategies(),
            "diagnosi": lambda args, adm: a.text_diagnostics(),
            "posizioni": lambda args, adm: a.text_positions(),
            "operazioni": lambda args, adm: a.text_trades(),
            "performance": lambda args, adm: a.text_performance(),
            "report": lambda args, adm: a.text_report(),
            "rischio": lambda args, adm: a.text_risk(),
            "pausa": lambda args, adm: a.pause(),
            "riprendi": lambda args, adm: a.resume(args),
            "chiudi": lambda args, adm: a.close(args[0]) if args else "Uso: /chiudi BTC",
            "modalita": lambda args, adm: a.text_mode(),
            "config": lambda args, adm: a.text_config(),
        }
        # alias compatibili con il prototipo precedente
        self.commands["analizza"] = self.commands["analisi"]
        self.commands["watch"] = self.commands["watchlist"]
        self.commands["wallet"] = self.commands["posizioni"]
        self.commands["journal"] = self.commands["operazioni"]

    def handle(self, command: str, args: list[str], user_id: int | None) -> str:
        command = command.lower().lstrip("/").split("@")[0]
        if not self.access.can_use(user_id):
            log.warning("accesso Telegram negato", extra={"data": {"user_id": user_id, "command": command}})
            return "⛔ Accesso non autorizzato."
        if command in ADMIN_COMMANDS and not self.access.is_admin(user_id):
            return "⛔ Comando riservato agli amministratori."
        handler = self.commands.get(command)
        if handler is None:
            return "Comando non riconosciuto. Usa /help per l'elenco."
        try:
            return handler([a for a in args if a], self.access.is_admin(user_id))
        except Exception as exc:  # noqa: BLE001 - l'utente riceve sempre una risposta
            log.exception("errore nel comando Telegram", extra={"data": {"command": command}})
            return f"❌ Non è stato possibile completare il comando ({type(exc).__name__}). Riprova più tardi."


class ConflictMonitor:
    """Telegram risponde 409 (Conflict) quando due processi usano lo stesso token.

    Succede se ATLAS gira sia nel Codespace sia sul server. Si registra l'evento e si
    avvisa l'utente al massimo una volta all'ora (niente raffiche di messaggi).
    """

    def __init__(self, atlas: Atlas, every_seconds: int = 3600, clock=None) -> None:
        import time

        self.atlas = atlas
        self.every = every_seconds
        self.clock = clock or time.time
        self._last: float | None = None

    def report(self) -> bool:
        now = self.clock()
        if self._last is not None and now - self._last < self.every:
            return False
        self._last = now
        self.atlas.db.log_event("telegram_conflict", "un'altra istanza usa lo stesso token Telegram", level="CRITICAL")
        log.critical("conflitto Telegram: un'altra istanza usa lo stesso token")
        self.atlas.notifier.send(
            "⚠️ ATLAS — Due istanze attive con lo stesso bot Telegram\n\n"
            "Telegram segnala un conflitto: ATLAS sta girando in due posti (es. Codespace e server).\n"
            "Ferma quella che non deve restare attiva (nel Codespace: Ctrl+C nel terminale di ATLAS)."
        )
        return True


def build_application(atlas: Atlas, on_startup: Callable[[], Awaitable[None]] | None = None):
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes

    s = atlas.settings
    router = CommandRouter(atlas, AccessControl(s.telegram_allowed_users, s.telegram_admin_users))

    async def dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None or update.message.text is None:
            return
        parts = update.message.text.split()
        user_id = update.effective_user.id if update.effective_user else None
        text = await asyncio.to_thread(router.handle, parts[0], parts[1:], user_id)
        for i in range(0, len(text), 4000):
            await update.message.reply_text(text[i : i + 4000], disable_web_page_preview=True)

    async def post_init(app: Application) -> None:
        if on_startup:
            await on_startup()

    conflict = ConflictMonitor(atlas)

    async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        from telegram.error import Conflict

        if isinstance(context.error, Conflict):
            await asyncio.to_thread(conflict.report)
        else:
            log.warning("errore Telegram", extra={"data": {"error": type(context.error).__name__}})

    app = Application.builder().token(s.telegram_token).post_init(post_init).build()
    app.add_handler(CommandHandler(list(router.commands), dispatch))
    app.add_error_handler(on_error)
    app.bot_data["router"] = router
    return app


def run_bot(atlas: Atlas, on_startup: Callable[[], Awaitable[None]] | None = None) -> None:
    from telegram import Update

    app = build_application(atlas, on_startup)
    log.info("bot Telegram avviato")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
