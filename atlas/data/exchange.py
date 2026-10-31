"""Accesso ai dati di mercato Kraken tramite CCXT, in SOLA LETTURA.

Questo modulo non contiene, e non deve mai contenere, chiamate che creano,
modificano o cancellano ordini né prelievi. Gli endpoint pubblici (candele,
ticker, book, mercati) non richiedono credenziali; il saldo reale richiede una
API key con il solo permesso "Query Funds".
"""

from __future__ import annotations

import time
from typing import Any, Callable, Protocol

from atlas.domain import MarketRules
from atlas.logging_setup import get_logger, register_secret

log = get_logger(__name__)


class ExchangeUnavailable(RuntimeError):
    """Exchange non raggiungibile dopo i tentativi previsti."""


class MarketDataSource(Protocol):
    """Interfaccia minima per una fonte dati (reale, simulata o storica)."""

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int, since: int | None = None) -> list[list]: ...

    def fetch_ticker(self, symbol: str) -> dict: ...

    def market_rules(self, symbol: str) -> MarketRules: ...

    def ping(self) -> bool: ...


# Metodi CCXT consentiti: solo lettura. Qualsiasi altro accesso è bloccato.
_READ_ONLY_METHODS = frozenset(
    {
        "load_markets",
        "fetch_ohlcv",
        "fetch_ticker",
        "fetch_order_book",
        "fetch_time",
        "fetch_status",
        "fetch_balance",
    }
)


class ReadOnlyExchange:
    """Proxy che espone esclusivamente i metodi CCXT di lettura."""

    def __init__(self, exchange: Any) -> None:
        object.__setattr__(self, "_exchange", exchange)

    def __getattr__(self, name: str) -> Any:
        if name in _READ_ONLY_METHODS or name in {"markets", "id", "rateLimit"}:
            return getattr(self._exchange, name)
        raise PermissionError(f"Metodo exchange '{name}' bloccato: ATLAS usa Kraken in sola lettura.")

    def __setattr__(self, name: str, value: Any) -> None:  # pragma: no cover - difensivo
        raise PermissionError("ReadOnlyExchange è immutabile.")


def with_retries(
    func: Callable[[], Any],
    *,
    retries: int,
    base_delay: float = 1.0,
    retry_on: tuple[type[BaseException], ...] = (),
    sleep: Callable[[float], None] = time.sleep,
    what: str = "richiesta",
) -> Any:
    """Esegue ``func`` con backoff esponenziale sugli errori transitori."""
    attempt = 0
    while True:
        try:
            return func()
        except retry_on as exc:
            attempt += 1
            if attempt > retries:
                raise ExchangeUnavailable(f"{what}: fallita dopo {retries} tentativi ({type(exc).__name__})") from exc
            delay = base_delay * (2 ** (attempt - 1))
            log.warning(f"{what}: errore transitorio, nuovo tentativo tra {delay:.0f}s", extra={"data": {"error": type(exc).__name__, "attempt": attempt}})
            sleep(delay)


class LockedSource:
    """Serializza l'accesso a una fonte dati condivisa tra thread (bot + scheduler)."""

    def __init__(self, inner: Any) -> None:
        import threading

        self._inner = inner
        self._lock = threading.RLock()

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def locked(*args, **kwargs):
            with self._lock:
                return attr(*args, **kwargs)

        return locked


class KrakenDataSource:
    """Client Kraken in sola lettura con rate limit, timeout e retry."""

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        timeout_ms: int = 15000,
        max_retries: int = 4,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        import ccxt  # import locale: i test offline non richiedono ccxt

        self._ccxt = ccxt
        config: dict[str, Any] = {"enableRateLimit": True, "timeout": timeout_ms}
        if api_key and api_secret:
            register_secret(api_key)
            register_secret(api_secret)
            config.update({"apiKey": api_key, "secret": api_secret})
        self.has_credentials = bool(api_key and api_secret)
        self._exchange = ReadOnlyExchange(ccxt.kraken(config))
        self._max_retries = max_retries
        self._sleep = sleep
        self._markets_loaded_at = 0.0
        self._transient = (ccxt.NetworkError, ccxt.RateLimitExceeded, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout)

    def _call(self, what: str, func: Callable[[], Any]) -> Any:
        return with_retries(func, retries=self._max_retries, retry_on=self._transient, sleep=self._sleep, what=what)

    def _ensure_markets(self) -> None:
        if time.time() - self._markets_loaded_at > 6 * 3600:
            self._call("load_markets", lambda: self._exchange.load_markets(True))
            self._markets_loaded_at = time.time()

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int, since: int | None = None) -> list[list]:
        return self._call(
            f"ohlcv {symbol} {timeframe}",
            lambda: self._exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit),
        )

    def fetch_ticker(self, symbol: str) -> dict:
        return self._call(f"ticker {symbol}", lambda: self._exchange.fetch_ticker(symbol))

    def market_rules(self, symbol: str) -> MarketRules:
        self._ensure_markets()
        market = self._exchange.markets.get(symbol)
        if market is None:
            raise ValueError(f"Coppia {symbol} non disponibile su Kraken")
        precision = market.get("precision") or {}
        limits = market.get("limits") or {}
        # CCXT recente usa la modalità TICK_SIZE: precision è già il passo.
        amount_step = float(precision.get("amount") or 1e-8)
        price_step = float(precision.get("price") or 1e-8)
        if amount_step >= 1 and float(amount_step).is_integer() and amount_step > 1:
            amount_step = 10 ** (-int(amount_step))  # modalità DECIMAL_PLACES
        return MarketRules(
            symbol=symbol,
            amount_step=amount_step,
            price_step=price_step,
            min_amount=float((limits.get("amount") or {}).get("min") or 0.0),
            min_cost=float((limits.get("cost") or {}).get("min") or 0.0),
        )

    def fetch_balance(self) -> dict[str, float]:
        """Saldo reale (richiede API key con permesso Query Funds)."""
        if not self.has_credentials:
            raise PermissionError("Credenziali Kraken non configurate (necessarie solo per il saldo reale).")
        balance = self._call("balance", self._exchange.fetch_balance)
        totals = balance.get("total", {}) or {}
        return {k: float(v) for k, v in totals.items() if v}

    def ping(self) -> bool:
        try:
            status = self._call("status", self._exchange.fetch_status)
            return (status or {}).get("status", "ok") == "ok"
        except Exception:  # noqa: BLE001 - un health check non deve sollevare
            return False
