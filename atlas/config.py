"""Configurazione di ATLAS tramite variabili d'ambiente.

Tutti i parametri hanno valori predefiniti prudenti. Le credenziali NON hanno
mai un valore predefinito e non vengono mai stampate (vedi ``Settings.redacted``).

Il trading reale è disabilitato per costruzione: anche impostando
``ATLAS_MODE=live`` la configurazione viene rifiutata finché la procedura
descritta in ``docs/LIVE_TRADING_POLICY.md`` non viene completata. Nella
versione 1 l'esecuzione reale non è implementata (vedi ``atlas/execution/live.py``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

try:  # python-dotenv è opzionale: in produzione si usano variabili d'ambiente reali
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


class ConfigError(ValueError):
    """Configurazione non valida."""


SECRET_FIELDS = {"kraken_api_key", "kraken_api_secret", "telegram_token"}


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _float(name: str, default: float) -> float:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return float(raw.replace(",", "."))
    except ValueError as exc:
        raise ConfigError(f"{name} deve essere un numero (valore: {raw!r})") from exc


def _int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} deve essere un intero (valore: {raw!r})") from exc


def _bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "si", "sì", "on"}


def _list(name: str, default: list[str]) -> list[str]:
    raw = _env(name)
    if raw is None:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _int_set(name: str) -> frozenset[int]:
    values = set()
    for item in _list(name, []):
        try:
            values.add(int(item))
        except ValueError as exc:
            raise ConfigError(f"{name}: '{item}' non è un ID Telegram valido") from exc
    return frozenset(values)


@dataclass(frozen=True)
class Settings:
    # --- Generale -----------------------------------------------------------
    mode: str = "paper"
    data_dir: Path = Path("data")
    log_level: str = "INFO"
    log_json: bool = True
    quote_currency: str = "EUR"
    watchlist: tuple[str, ...] = ("BTC/EUR", "ETH/EUR", "SOL/EUR")

    # --- Capitale e costi (paper) ------------------------------------------
    initial_capital: float = 100.0
    taker_fee_pct: float = 0.40   # Kraken Pro, livello base (taker)
    maker_fee_pct: float = 0.25
    slippage_pct: float = 0.05
    default_spread_pct: float = 0.10  # usato se il book non è disponibile
    min_order_cost: float = 5.0       # minimo di sicurezza in valuta quotata

    # --- Analisi ------------------------------------------------------------
    timeframe: str = "1h"
    higher_timeframe: str = "4h"
    candles_limit: int = 720   # massimo Kraken: serve per la convergenza dell'EMA200
    market_reference: str = "BTC/EUR"

    # --- Decisione / scoring ----------------------------------------------
    min_score: float = 65.0
    min_reward_risk: float = 1.8      # netto di commissioni
    strategies: tuple[str, ...] = ("trend_pullback", "breakout")

    # --- Rischio ------------------------------------------------------------
    risk_per_trade_pct: float = 1.0
    max_position_pct: float = 50.0
    max_exposure_pct: float = 80.0
    max_open_positions: int = 2
    max_daily_loss_pct: float = 3.0
    max_drawdown_pct: float = 15.0
    max_consecutive_losses: int = 4
    cooldown_hours_after_losses: int = 24
    max_correlated_risk_pct: float = 1.5
    correlation_threshold: float = 0.8
    max_spread_pct: float = 0.5
    max_bar_move_atr: float = 4.0
    max_data_age_minutes: int = 180
    max_consecutive_errors: int = 5

    # --- Gestione posizione ---------------------------------------------
    trailing_activation_r: float = 1.0
    trailing_atr_multiple: float = 2.5
    time_stop_bars: int = 48

    # --- Scheduler -----------------------------------------------------
    cycle_interval_seconds: int = 300
    daily_report_hour_utc: int = 20

    # --- Telegram -----------------------------------------------------------
    telegram_token: str | None = field(default=None, repr=False)
    telegram_chat_id: str | None = None
    telegram_allowed_users: frozenset[int] = frozenset()
    telegram_admin_users: frozenset[int] = frozenset()

    # --- Kraken (sola lettura) -------------------------------------------
    kraken_api_key: str | None = field(default=None, repr=False)
    kraken_api_secret: str | None = field(default=None, repr=False)
    exchange_timeout_ms: int = 15000
    exchange_max_retries: int = 4

    # ------------------------------------------------------------------
    @property
    def db_path(self) -> Path:
        return self.data_dir / "atlas.db"

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_token and self.telegram_chat_id)

    def redacted(self) -> dict:
        """Configurazione senza segreti, sicura da mostrare o registrare."""
        out = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name in SECRET_FIELDS:
                value = "***configurato***" if value else "non configurato"
            elif isinstance(value, (frozenset, tuple)):
                value = sorted(value) if isinstance(value, frozenset) else list(value)
            elif isinstance(value, Path):
                value = str(value)
            out[f.name] = value
        return out

    def validate(self) -> None:
        errors: list[str] = []
        if self.mode != "paper":
            errors.append(
                "ATLAS_MODE diverso da 'paper' non è consentito in questa versione: "
                "il trading reale richiede la procedura in docs/LIVE_TRADING_POLICY.md."
            )
        if self.initial_capital <= 0:
            errors.append("ATLAS_INITIAL_CAPITAL deve essere > 0")
        if not 0 < self.risk_per_trade_pct <= 2:
            errors.append("ATLAS_RISK_PER_TRADE_PCT deve essere tra 0 e 2")
        if not 0 < self.max_position_pct <= 100:
            errors.append("ATLAS_MAX_POSITION_PCT deve essere tra 0 e 100")
        if not 0 < self.max_exposure_pct <= 100:
            errors.append("ATLAS_MAX_EXPOSURE_PCT deve essere tra 0 e 100")
        if self.max_open_positions < 1:
            errors.append("ATLAS_MAX_OPEN_POSITIONS deve essere >= 1")
        if self.min_reward_risk < 1:
            errors.append("ATLAS_MIN_REWARD_RISK deve essere >= 1")
        if not 0 <= self.min_score <= 100:
            errors.append("ATLAS_MIN_SCORE deve essere tra 0 e 100")
        for pct_name in ("taker_fee_pct", "maker_fee_pct", "slippage_pct", "default_spread_pct"):
            if not 0 <= getattr(self, pct_name) < 5:
                errors.append(f"{pct_name} fuori intervallo")
        if not 600 <= self.candles_limit <= 720:
            errors.append(
                "ATLAS_CANDLES_LIMIT deve essere tra 600 e 720: con meno candele l'EMA200 non converge "
                "e l'analisi live diverge dal backtest (720 è il massimo restituito da Kraken)"
            )
        if self.cycle_interval_seconds < 30:
            errors.append("ATLAS_CYCLE_INTERVAL_SECONDS deve essere >= 30 (rate limit Kraken)")
        for symbol in self.watchlist:
            if "/" not in symbol:
                errors.append(f"Simbolo watchlist non valido: {symbol} (formato BASE/QUOTE)")
        if errors:
            raise ConfigError("Configurazione non valida:\n- " + "\n- ".join(errors))


def normalize_symbol(symbol: str, quote: str = "EUR") -> str:
    symbol = symbol.strip().upper()
    if "/" not in symbol:
        symbol = f"{symbol}/{quote}"
    return symbol


def load_settings(env_file: str | None = ".env") -> Settings:
    """Carica e valida la configurazione dall'ambiente."""
    if load_dotenv is not None and env_file and Path(env_file).exists():
        load_dotenv(env_file, override=False)

    quote = (_env("ATLAS_QUOTE_CURRENCY", "EUR") or "EUR").upper()
    settings = Settings(
        mode=(_env("ATLAS_MODE", "paper") or "paper").lower(),
        data_dir=Path(_env("ATLAS_DATA_DIR", "data") or "data"),
        log_level=(_env("ATLAS_LOG_LEVEL", "INFO") or "INFO").upper(),
        log_json=_bool("ATLAS_LOG_JSON", True),
        quote_currency=quote,
        watchlist=tuple(
            normalize_symbol(s, quote)
            for s in _list("ATLAS_WATCHLIST", ["BTC/EUR", "ETH/EUR", "SOL/EUR"])
        ),
        initial_capital=_float("ATLAS_INITIAL_CAPITAL", 100.0),
        taker_fee_pct=_float("ATLAS_TAKER_FEE_PCT", 0.40),
        maker_fee_pct=_float("ATLAS_MAKER_FEE_PCT", 0.25),
        slippage_pct=_float("ATLAS_SLIPPAGE_PCT", 0.05),
        default_spread_pct=_float("ATLAS_DEFAULT_SPREAD_PCT", 0.10),
        min_order_cost=_float("ATLAS_MIN_ORDER_COST", 5.0),
        timeframe=_env("ATLAS_TIMEFRAME", "1h") or "1h",
        higher_timeframe=_env("ATLAS_HIGHER_TIMEFRAME", "4h") or "4h",
        candles_limit=_int("ATLAS_CANDLES_LIMIT", 720),
        market_reference=normalize_symbol(_env("ATLAS_MARKET_REFERENCE", "BTC/EUR") or "BTC", quote),
        min_score=_float("ATLAS_MIN_SCORE", 65.0),
        min_reward_risk=_float("ATLAS_MIN_REWARD_RISK", 1.8),
        strategies=tuple(_list("ATLAS_STRATEGIES", ["trend_pullback", "breakout"])),
        risk_per_trade_pct=_float("ATLAS_RISK_PER_TRADE_PCT", 1.0),
        max_position_pct=_float("ATLAS_MAX_POSITION_PCT", 50.0),
        max_exposure_pct=_float("ATLAS_MAX_EXPOSURE_PCT", 80.0),
        max_open_positions=_int("ATLAS_MAX_OPEN_POSITIONS", 2),
        max_daily_loss_pct=_float("ATLAS_MAX_DAILY_LOSS_PCT", 3.0),
        max_drawdown_pct=_float("ATLAS_MAX_DRAWDOWN_PCT", 15.0),
        max_consecutive_losses=_int("ATLAS_MAX_CONSECUTIVE_LOSSES", 4),
        cooldown_hours_after_losses=_int("ATLAS_COOLDOWN_HOURS", 24),
        max_correlated_risk_pct=_float("ATLAS_MAX_CORRELATED_RISK_PCT", 1.5),
        correlation_threshold=_float("ATLAS_CORRELATION_THRESHOLD", 0.8),
        max_spread_pct=_float("ATLAS_MAX_SPREAD_PCT", 0.5),
        max_bar_move_atr=_float("ATLAS_MAX_BAR_MOVE_ATR", 4.0),
        max_data_age_minutes=_int("ATLAS_MAX_DATA_AGE_MINUTES", 180),
        max_consecutive_errors=_int("ATLAS_MAX_CONSECUTIVE_ERRORS", 5),
        trailing_activation_r=_float("ATLAS_TRAILING_ACTIVATION_R", 1.0),
        trailing_atr_multiple=_float("ATLAS_TRAILING_ATR_MULTIPLE", 2.5),
        time_stop_bars=_int("ATLAS_TIME_STOP_BARS", 48),
        cycle_interval_seconds=_int("ATLAS_CYCLE_INTERVAL_SECONDS", 300),
        daily_report_hour_utc=_int("ATLAS_DAILY_REPORT_HOUR_UTC", 20),
        telegram_token=_env("TELEGRAM_TOKEN"),
        telegram_chat_id=_env("TELEGRAM_CHAT_ID"),
        telegram_allowed_users=_int_set("TELEGRAM_ALLOWED_USERS"),
        telegram_admin_users=_int_set("TELEGRAM_ADMIN_USERS"),
        kraken_api_key=_env("KRAKEN_API_KEY"),
        kraken_api_secret=_env("KRAKEN_API_SECRET"),
        exchange_timeout_ms=_int("ATLAS_EXCHANGE_TIMEOUT_MS", 15000),
        exchange_max_retries=_int("ATLAS_EXCHANGE_MAX_RETRIES", 4),
    )
    settings.validate()
    return settings
