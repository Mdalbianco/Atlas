"""Cancello di validazione delle strategie.

Lo stato di validazione è un file versionato nel repository
(``atlas/strategy/validation_status.json``), scritto dal comando
``python -m atlas validate`` e reso effettivo SOLO quando una persona lo
committa. Il programma in esecuzione non lo modifica mai: niente
auto-promozione di strategie.

Una strategia è "attiva" (portafoglio principale) solo se la sua versione
esatta (``nome@versione``) risulta ``validata``. Cambiare la logica o i
parametri richiede una nuova versione, che riparte da "non validata".
Le strategie non validate possono girare in portafogli OMBRA isolati
(un conto virtuale separato per ciascuna) per raccogliere evidenza senza
influenzare il portafoglio principale.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

STATUS_FILE = Path(__file__).with_name("validation_status.json")

# Criteri minimi per la promozione (fuori campione, dati reali, costi inclusi)
CRITERIA = {
    "min_oos_trades": 30,
    "min_expectancy_r": 0.05,
    "min_profit_factor": 1.15,
    "max_drawdown_pct": 15.0,
    "min_positive_folds_ratio": 0.5,
}

# Seconda condizione: evidenza in paper trading reale (portafoglio ombra), mai solo backtest
PAPER_CRITERIA = {
    "min_closed_trades": 20,
    "min_expectancy_r": 0.0,
    "min_days": 60,
}


@dataclass
class StrategyStatus:
    key: str
    status: str            # validata | respinta | non_validata
    reason: str = ""
    report: dict | None = None


def load_status(path: Path = STATUS_FILE) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("strategies", {})


def status_of(strategy, path: Path = STATUS_FILE, timeframe: str | None = None) -> StrategyStatus:
    """Stato di validazione di ``nome@versione``.

    Una validazione vale SOLO per il timeframe su cui è stata ottenuta: una strategia
    validata su 4h non risulta validata su 1h (e viceversa).
    """
    key = strategy.id
    entry = load_status(path).get(key)
    if entry is None:
        return StrategyStatus(key, "non_validata", "nessuna validazione registrata per questa versione")
    tf = entry.get("timeframe")
    if timeframe is not None and tf != timeframe:
        return StrategyStatus(key, "non_validata", f"validazione registrata per il timeframe {tf}, non per {timeframe}", entry)
    status = entry.get("status", "non_validata")
    if status == "validata" and not (entry.get("paper_evidence") or {}).get("passed"):
        return StrategyStatus(key, "in_osservazione", "backtest superato: serve ancora evidenza in paper trading (portafoglio ombra)", entry)
    return StrategyStatus(key, status, entry.get("reason", ""), entry)


def paper_evidence(shadow_db, since_days_min: int | None = None) -> dict:
    """Valuta i risultati REALI di paper trading di un portafoglio ombra rispetto a PAPER_CRITERIA."""
    from datetime import datetime, timezone

    from atlas.backtest.metrics import trade_metrics
    from atlas.performance.analyzer import closed_trades_frame

    df = closed_trades_frame(shadow_db)
    m = trade_metrics(df) if not df.empty else {"trades": 0}
    first = shadow_db.query("SELECT MIN(ts) t FROM equity")[0]["t"]
    days = (datetime.now(timezone.utc) - datetime.fromisoformat(first)).days if first else 0
    c = PAPER_CRITERIA
    fails = []
    if m.get("trades", 0) < c["min_closed_trades"]:
        fails.append(f"{m.get('trades', 0)} operazioni chiuse in paper (minimo {c['min_closed_trades']})")
    if (m.get("expectancy_r") or 0.0) <= c["min_expectancy_r"]:
        fails.append(f"expectancy in paper {m.get('expectancy_r') or 0:+.2f} R non positiva")
    if days < (since_days_min or c["min_days"]):
        fails.append(f"solo {days} giorni di paper trading (minimo {c['min_days']})")
    return {"passed": not fails, "reasons": fails, "trades": m.get("trades", 0), "expectancy_r": m.get("expectancy_r"), "days": days}


def split_active_shadow(strategies: list, require_validation: bool = True, path: Path = STATUS_FILE, timeframe: str | None = None) -> tuple[list, list]:
    if not require_validation:
        return list(strategies), []
    active = [s for s in strategies if status_of(s, path, timeframe).status == "validata"]
    shadow = [s for s in strategies if s not in active]
    return active, shadow


def evaluate_criteria(oos: dict, max_dd: float, positive_folds_ratio: float) -> tuple[bool, list[str]]:
    """Applica i criteri di promozione. Restituisce (superata, motivi di esclusione)."""
    c = CRITERIA
    fails = []
    n = oos.get("trades", 0)
    if n < c["min_oos_trades"]:
        fails.append(f"solo {n} operazioni fuori campione (minimo {c['min_oos_trades']})")
    exp = oos.get("expectancy_r") or 0.0
    if exp < c["min_expectancy_r"]:
        fails.append(f"expectancy {exp:+.3f} R sotto il minimo {c['min_expectancy_r']}")
    pf = oos.get("profit_factor") or 0.0
    if pf < c["min_profit_factor"]:
        fails.append(f"profit factor {pf:.2f} sotto il minimo {c['min_profit_factor']}")
    if max_dd > c["max_drawdown_pct"]:
        fails.append(f"drawdown {max_dd:.1f}% oltre il massimo {c['max_drawdown_pct']}%")
    if positive_folds_ratio < c["min_positive_folds_ratio"]:
        fails.append(f"solo il {positive_folds_ratio:.0%} dei periodi di test è positivo")
    return not fails, fails
