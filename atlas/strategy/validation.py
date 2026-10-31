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


def status_of(strategy, path: Path = STATUS_FILE) -> StrategyStatus:
    key = strategy.id
    entry = load_status(path).get(key)
    if entry is None:
        return StrategyStatus(key, "non_validata", "nessuna validazione registrata per questa versione")
    return StrategyStatus(key, entry.get("status", "non_validata"), entry.get("reason", ""), entry)


def split_active_shadow(strategies: list, require_validation: bool = True, path: Path = STATUS_FILE) -> tuple[list, list]:
    if not require_validation:
        return list(strategies), []
    active = [s for s in strategies if status_of(s, path).status == "validata"]
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
