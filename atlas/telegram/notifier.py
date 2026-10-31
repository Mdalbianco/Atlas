"""Invio di notifiche Telegram (sincrono, via Bot API HTTP).

È indipendente dal bot interattivo così che lo scheduler possa notificare
da un thread separato. Un errore di invio non interrompe mai il ciclo di
trading: viene solo registrato (senza token, oscurato dal logging).
"""

from __future__ import annotations

import time
from collections import deque
from typing import Protocol

from atlas.logging_setup import get_logger, register_secret

log = get_logger(__name__)

MAX_LEN = 4000  # limite Telegram 4096 caratteri


class Notifier(Protocol):
    def send(self, text: str) -> bool: ...


class NullNotifier:
    """Usato quando Telegram non è configurato: registra soltanto."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, text: str) -> bool:
        self.sent.append(text)
        log.info("notifica (Telegram non configurato)", extra={"data": {"text": text[:200]}})
        return False


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, timeout: float = 10.0, max_per_minute: int = 20) -> None:
        register_secret(token)
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_id = chat_id
        self._timeout = timeout
        self._max = max_per_minute
        self._sent: deque[float] = deque()

    def send(self, text: str) -> bool:
        import requests

        now = time.time()
        while self._sent and now - self._sent[0] > 60:
            self._sent.popleft()
        if len(self._sent) >= self._max:
            log.warning("notifica scartata: limite di messaggi al minuto raggiunto")
            return False
        chunks = [text[i : i + MAX_LEN] for i in range(0, len(text), MAX_LEN)] or [""]
        ok = True
        for chunk in chunks:
            for attempt in range(3):
                try:
                    r = requests.post(self._url, json={"chat_id": self._chat_id, "text": chunk, "disable_web_page_preview": True}, timeout=self._timeout)
                    if r.status_code == 429:
                        time.sleep(min(30, int(r.json().get("parameters", {}).get("retry_after", 5))))
                        continue
                    if r.ok:
                        break
                    log.warning("notifica Telegram rifiutata", extra={"data": {"status": r.status_code}})
                    ok = False
                    break
                except Exception as exc:  # noqa: BLE001
                    log.warning("errore di rete nell'invio Telegram", extra={"data": {"error": type(exc).__name__, "attempt": attempt + 1}})
                    time.sleep(2 ** attempt)
            else:
                ok = False
        self._sent.append(now)
        return ok


def build_notifier(settings) -> Notifier:
    if settings.telegram_enabled:
        return TelegramNotifier(settings.telegram_token, settings.telegram_chat_id)
    return NullNotifier()
