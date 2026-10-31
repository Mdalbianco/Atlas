"""Registro delle strategie versionate.

Promuovere una strategia (es. da ``in_validazione`` a ``validata``) è una
decisione umana documentata in ``docs/STRATEGIES.md``: richiede un report di
walk-forward su dati reali fuori campione. ATLAS non modifica mai da solo il
registro né il codice delle strategie.
"""

from __future__ import annotations

from atlas.strategy.base import Strategy
from atlas.strategy.breakout import VolumeBreakout
from atlas.strategy.trend_pullback import TrendPullback

STRATEGIES: dict[str, type[Strategy]] = {
    TrendPullback.name: TrendPullback,
    VolumeBreakout.name: VolumeBreakout,
}


def build_strategies(names: tuple[str, ...] | list[str], overrides: dict[str, dict] | None = None) -> list[Strategy]:
    overrides = overrides or {}
    out = []
    for name in names:
        if name not in STRATEGIES:
            raise ValueError(f"Strategia sconosciuta: {name}. Disponibili: {', '.join(STRATEGIES)}")
        out.append(STRATEGIES[name](**overrides.get(name, {})))
    return out


def describe() -> list[dict]:
    return [
        {"name": cls.name, "version": cls.version, "status": cls.status, "description": cls.description, "params": cls.default_params()}
        for cls in STRATEGIES.values()
    ]
