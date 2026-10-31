"""Esecuzione continua: scheduler dei cicli + bot Telegram + report giornaliero."""

from __future__ import annotations

import signal
import threading
from datetime import datetime, timezone

from atlas import __version__
from atlas.app import Atlas
from atlas.logging_setup import get_logger
from atlas.telegram import formatters as fmt

log = get_logger(__name__)


class Scheduler:
    def __init__(self, atlas: Atlas, interval_seconds: int, stop: threading.Event | None = None) -> None:
        self.atlas = atlas
        self.interval = interval_seconds
        self.stop = stop or threading.Event()

    def _maybe_daily_report(self) -> None:
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        if now.hour >= self.atlas.settings.daily_report_hour_utc and self.atlas.db.get_state("last_daily_report") != today:
            self.atlas.db.set_state("last_daily_report", today)
            try:
                self.atlas.notifier.send("🗓 ATLAS — Riepilogo giornaliero\n\n" + self.atlas.text_status() + "\n\n" + self.atlas.text_performance())
            except Exception:  # noqa: BLE001
                log.exception("report giornaliero non inviato")

    def loop(self) -> None:
        log.info("scheduler avviato", extra={"data": {"interval_s": self.interval}})
        while not self.stop.is_set():
            started = datetime.now(timezone.utc)
            rep = self.atlas.cycle.run_once()
            log.info(
                "ciclo completato",
                extra={"data": {"ok": rep.ok, "analyzed": len(rep.analyzed), "opened": len(rep.opened), "closed": len(rep.closed), "errors": rep.errors[:3], "equity": rep.equity}},
            )
            self._maybe_daily_report()
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            self.stop.wait(max(5.0, self.interval - elapsed))
        log.info("scheduler fermato")


def startup_message(atlas: Atlas) -> str:
    st = atlas.cycle.account.state()
    open_n = len(st.positions)
    return "\n".join(
        [
            f"🚀 ATLAS v{__version__} avviato — PAPER TRADING",
            "",
            *fmt.portfolio_summary(st, atlas.cycle.account.initial_capital, atlas.ccy),
            f"Posizioni riprese dopo l'avvio: {open_n}" if open_n else "Nessuna posizione aperta.",
            "",
            "Usa /help per i comandi.",
        ]
    )


def run_forever(atlas: Atlas) -> None:
    stop = threading.Event()

    def _graceful(signum, _frame):
        log.info("segnale di arresto ricevuto", extra={"data": {"signal": signum}})
        stop.set()

    scheduler = Scheduler(atlas, atlas.settings.cycle_interval_seconds, stop)
    thread = threading.Thread(target=scheduler.loop, name="atlas-scheduler", daemon=True)
    atlas.db.log_event("startup", f"ATLAS {__version__} avviato")
    atlas.notifier.send(startup_message(atlas))

    if atlas.settings.telegram_enabled:
        from atlas.telegram.bot import run_bot

        thread.start()
        try:
            run_bot(atlas)  # blocca fino a SIGINT/SIGTERM (gestiti da python-telegram-bot)
        finally:
            stop.set()
            thread.join(timeout=60)
    else:
        log.warning("Telegram non configurato: solo scheduler (notifiche nei log)")
        signal.signal(signal.SIGTERM, _graceful)
        signal.signal(signal.SIGINT, _graceful)
        thread.start()
        while thread.is_alive():
            thread.join(timeout=1)
    atlas.db.log_event("shutdown", "ATLAS arrestato in modo ordinato")
    atlas.db.close()
