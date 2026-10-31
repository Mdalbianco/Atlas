"""Diagnosi completa dell'installazione: ``python -m atlas doctor``.

Pensato per essere eseguito dall'utente nel Codespace o sul server. Non stampa
mai segreti: del token Telegram mostra solo il nome del bot restituito da
Telegram, delle chiavi Kraken solo se sono presenti.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    warn: bool = False   # True = avviso non bloccante


def run_checks(settings, network: bool = True, source=None) -> list[Check]:
    from atlas import __version__
    from atlas.data.exchange import ReadOnlyExchange
    from atlas.strategy.registry import STRATEGIES, build_strategies
    from atlas.strategy.validation import split_active_shadow, status_of

    out: list[Check] = []
    s = settings
    out.append(Check("Versione", True, f"ATLAS {__version__}, Python {sys.version.split()[0]}"))
    out.append(Check("Modalità", s.mode == "paper", "PAPER TRADING" if s.mode == "paper" else f"modalità non ammessa: {s.mode}"))

    # blocco ordini reali
    try:
        from atlas.execution.live import LiveBroker, LiveTradingDisabled

        try:
            LiveBroker()
            out.append(Check("Ordini reali", False, "LiveBroker istanziabile: NON SICURO"))
        except LiveTradingDisabled:
            out.append(Check("Ordini reali", True, "bloccati (LiveBroker disabilitato, client Kraken in sola lettura)"))
    except Exception as exc:  # noqa: BLE001
        out.append(Check("Ordini reali", False, f"verifica non riuscita: {exc}"))

    # strategie e cancello di validazione
    candidates = build_strategies(s.strategies)
    active, shadow = split_active_shadow(candidates, s.require_validation, timeframe=s.timeframe)
    missing = sorted(set(STRATEGIES) - set(s.strategies))
    out.append(Check("Strategie", True, f"{len(candidates)} candidate: {', '.join(x.name for x in candidates)}", warn=bool(missing)))
    if missing:
        out[-1].detail += f" — NON incluse: {', '.join(missing)} (controlla ATLAS_STRATEGIES nel .env)"
    out.append(Check("Validazione obbligatoria", s.require_validation, "attiva" if s.require_validation else "DISATTIVATA (ATLAS_REQUIRE_VALIDATION=false)", warn=not s.require_validation))
    out.append(Check("Portafoglio principale", True, f"strategie attive: {', '.join(x.name for x in active) or 'nessuna (nessuna validata)'}"))
    out.append(Check("Portafogli ombra", s.shadow_strategies or not shadow,
                     f"{len(shadow)} in osservazione: {', '.join(x.name for x in shadow)}" if s.shadow_strategies else "DISATTIVATI (ATLAS_SHADOW_STRATEGIES=false)",
                     warn=not s.shadow_strategies))
    for st in candidates:
        vs = status_of(st, timeframe=s.timeframe)
        out.append(Check(f"  {st.id}", True, vs.status))

    # cartella dati e istanze
    try:
        s.data_dir.mkdir(parents=True, exist_ok=True)
        probe = s.data_dir / ".doctor-probe"
        probe.write_text("ok")
        probe.unlink()
        out.append(Check("Cartella dati", True, f"{s.data_dir.resolve()} scrivibile"))
    except OSError as exc:
        out.append(Check("Cartella dati", False, f"{s.data_dir}: {exc}"))
    lock = s.data_dir / "atlas.lock"
    running = False
    if lock.exists():
        import fcntl

        with open(lock, "a+") as fh:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except BlockingIOError:
                running = True
    out.append(Check("Istanza ATLAS su questa cartella", True, "in esecuzione" if running else "nessuna in esecuzione"))
    db_path = s.db_path
    if db_path.exists():
        from atlas.storage.db import Database

        db = Database(db_path)
        cash = db.get_state("cash")
        hb = db.get_state("heartbeat")
        shadows = sorted(p.stem for p in (s.data_dir / "shadow").glob("*.db"))
        out.append(Check("Database", True, f"capitale principale {float(cash):.2f}, ultimo heartbeat {hb or 'mai'}, book ombra su disco: {', '.join(shadows) or 'nessuno'}"))
        db.close()
    else:
        out.append(Check("Database", True, "non ancora creato (verrà creato al primo avvio)"))

    # segreti: solo presenza
    env_file = Path(".env")
    if env_file.exists():
        mode = env_file.stat().st_mode & 0o777
        out.append(Check("Permessi .env", mode & 0o077 == 0, f"{oct(mode)}" + ("" if mode & 0o077 == 0 else " — consigliato: chmod 600 .env"), warn=mode & 0o077 != 0))
    out.append(Check("Telegram configurato", s.telegram_enabled, "sì" if s.telegram_enabled else "no (TELEGRAM_TOKEN/TELEGRAM_CHAT_ID mancanti)", warn=not s.telegram_enabled))
    out.append(Check("Utenti autorizzati", bool(s.telegram_allowed_users | s.telegram_admin_users),
                     f"{len(s.telegram_allowed_users | s.telegram_admin_users)} ID ({len(s.telegram_admin_users)} admin)", warn=not (s.telegram_allowed_users | s.telegram_admin_users)))
    out.append(Check("Chiavi Kraken", True, "presenti (solo lettura saldo)" if s.kraken_api_key else "assenti (non necessarie)"))

    if not network:
        return out

    # Kraken
    try:
        from atlas.data.market_data import MarketDataService

        if source is None:
            from atlas.data.exchange import KrakenDataSource

            source = KrakenDataSource(timeout_ms=s.exchange_timeout_ms, max_retries=1)
            out.append(Check("Client Kraken", isinstance(source._exchange, ReadOnlyExchange), "proxy di sola lettura attivo"))
        svc = MarketDataService(source, s.max_data_age_minutes)
        for sym in s.watchlist:
            df, _ = svc.candles(sym, s.timeframe, s.candles_limit)
            t = svc.ticker(sym)
            out.append(Check(f"Kraken {sym}", True, f"{len(df)} candele {s.timeframe}, ultimo prezzo {t['last']}"))
    except Exception as exc:  # noqa: BLE001
        out.append(Check("Kraken", False, f"non raggiungibile o dati non validi: {type(exc).__name__}: {str(exc)[:120]}"))

    # Telegram: getMe (verifica il token senza mostrarlo)
    if s.telegram_enabled:
        try:
            import requests

            r = requests.get(f"https://api.telegram.org/bot{s.telegram_token}/getMe", timeout=15)
            data = r.json()
            if data.get("ok"):
                out.append(Check("Telegram", True, f"token valido, bot @{data['result'].get('username')}"))
            else:
                out.append(Check("Telegram", False, f"token rifiutato da Telegram ({data.get('error_code')})"))
        except Exception as exc:  # noqa: BLE001
            out.append(Check("Telegram", False, f"non raggiungibile: {type(exc).__name__}"))
    return out


def render(checks: list[Check]) -> tuple[str, int]:
    lines = ["ATLAS — diagnosi dell'installazione", ""]
    failed = 0
    for c in checks:
        icon = "✅" if c.ok and not c.warn else ("⚠️ " if c.ok or c.warn else "❌")
        if not c.ok and not c.warn:
            failed += 1
        lines.append(f"{icon} {c.name}: {c.detail}")
    lines.append("")
    lines.append("Esito: tutto a posto." if failed == 0 else f"Esito: {failed} problemi da risolvere.")
    return "\n".join(lines), (0 if failed == 0 else 1)
