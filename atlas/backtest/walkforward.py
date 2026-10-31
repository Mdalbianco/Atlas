"""Validazione cronologica: split train/validazione/test e walk-forward.

Principi anti-overfitting adottati:
- griglie di parametri PICCOLE e definite a priori (niente ricerca esaustiva);
- selezione solo sul periodo di training, con numero minimo di operazioni;
- il periodo di test si usa una sola volta, alla fine, per il report;
- nel walk-forward ogni finestra di test è successiva alla propria finestra
  di training; i risultati fuori campione sono concatenati;
- si riporta la degradazione train → test e la stabilità dei parametri scelti.
Gli indicatori sono causali: lo storico precedente a una finestra serve solo
come riscaldamento e non introduce informazioni future.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, replace

import pandas as pd

from atlas.backtest.engine import Backtester, BacktestConfig, BacktestResult
from atlas.backtest.metrics import full_report, trade_metrics
from atlas.strategy.registry import build_strategies

DEFAULT_GRID: dict[str, list] = {
    "min_score": [60.0, 65.0, 70.0],
    "trend_pullback.target_r": [2.0, 2.5],
    "breakout.target_r": [2.0, 2.5],
}


@dataclass
class Candidate:
    params: dict
    result: BacktestResult
    objective: float


def _timeline(data: dict[str, pd.DataFrame]) -> list[int]:
    return sorted(set().union(*[set(df["timestamp"].astype("int64")) for df in data.values()]))


def chronological_split(data: dict[str, pd.DataFrame], fractions=(0.6, 0.2, 0.2), warmup_bars: int = 900) -> dict[str, tuple[int, int]]:
    tl = _timeline(data)
    usable = tl[warmup_bars:]
    if len(usable) < 100:
        raise ValueError("Storico insufficiente per lo split cronologico")
    n = len(usable)
    a = int(n * fractions[0])
    b = int(n * (fractions[0] + fractions[1]))
    return {
        "train": (usable[0], usable[a]),
        "validation": (usable[a], usable[b]),
        "test": (usable[b], usable[-1] + 1),
    }


def _apply(params: dict, base: BacktestConfig, strategy_names) -> tuple[BacktestConfig, list]:
    cfg = base
    overrides: dict[str, dict] = {}
    for key, value in params.items():
        if key == "min_score":
            cfg = replace(cfg, min_score=value)
        elif "." in key:
            strat, p = key.split(".", 1)
            overrides.setdefault(strat, {})[p] = value
    names = list(strategy_names)
    return cfg, build_strategies(names, {k: v for k, v in overrides.items() if k in names})


def objective(result: BacktestResult, min_trades: int) -> float:
    """Expectancy in R penalizzata se le operazioni sono poche."""
    m = trade_metrics(result.trades)
    n = m.get("trades", 0)
    if n == 0:
        return -1.0
    exp_r = m["expectancy_r"] or 0.0
    return exp_r * min(1.0, n / min_trades)


def grid_search(data, base: BacktestConfig, strategy_names, window: tuple[int, int], grid: dict | None = None, min_trades: int = 15, cache: dict | None = None) -> list[Candidate]:
    grid = grid or DEFAULT_GRID
    cache = cache if cache is not None else {}
    keys = [k for k in grid if k == "min_score" or k.split(".")[0] in strategy_names]
    out = []
    for combo in itertools.product(*[grid[k] for k in keys]):
        params = dict(zip(keys, combo))
        cfg, strategies = _apply(params, base, strategy_names)
        res = Backtester(strategies, cfg).run(data, *window, cache=cache)
        out.append(Candidate(params, res, objective(res, min_trades)))
    return sorted(out, key=lambda c: c.objective, reverse=True)


def validate(data, base: BacktestConfig, strategy_names, grid: dict | None = None, min_trades: int = 15) -> dict:
    """Ottimizza sul training, verifica su validazione, riporta il test una sola volta."""
    split = chronological_split(data)
    cache: dict = {}
    ranked = grid_search(data, base, strategy_names, split["train"], grid, min_trades, cache)
    best = ranked[0]
    cfg, strategies = _apply(best.params, base, strategy_names)
    val = Backtester(strategies, cfg).run(data, *split["validation"], cache=cache)
    test = Backtester(strategies, cfg).run(data, *split["test"], cache=cache)
    default_cfg, default_strats = _apply({}, base, strategy_names)
    default_test = Backtester(default_strats, default_cfg).run(data, *split["test"], cache=cache)
    train_rep, val_rep, test_rep = full_report(best.result), full_report(val), full_report(test)
    return {
        "split": {k: [pd.to_datetime(a, unit="ms", utc=True).isoformat(), pd.to_datetime(b, unit="ms", utc=True).isoformat()] for k, (a, b) in split.items()},
        "best_params": best.params,
        "ranking": [{"params": c.params, "objective": round(c.objective, 4), "trades": len(c.result.trades)} for c in ranked],
        "train": train_rep,
        "validation": val_rep,
        "test": test_rep,
        "test_default_params": full_report(default_test),
        "degradation_expectancy_r": _deg(train_rep, test_rep),
        "warnings": _warnings(train_rep, val_rep, test_rep),
    }


def walk_forward(data, base: BacktestConfig, strategy_names, train_bars: int = 2000, test_bars: int = 500, warmup_bars: int = 900, grid: dict | None = None, min_trades: int = 15) -> dict:
    tl = _timeline(data)
    folds = []
    oos_trades = []
    cache: dict = {}
    start = warmup_bars
    while start + train_bars + test_bars <= len(tl):
        tr = (tl[start], tl[start + train_bars])
        te_end = start + train_bars + test_bars
        te = (tl[start + train_bars], tl[te_end] if te_end < len(tl) else tl[-1] + 1)
        ranked = grid_search(data, base, strategy_names, tr, grid, min_trades, cache)
        best = ranked[0]
        cfg, strategies = _apply(best.params, base, strategy_names)
        res = Backtester(strategies, cfg).run(data, *te, cache=cache)
        rep = full_report(res)
        folds.append({"train_window": tr, "test_window": te, "params": best.params, "train_objective": best.objective, "test": rep})
        if not res.trades.empty:
            oos_trades.append(res.trades)
        start += test_bars
    all_oos = pd.concat(oos_trades, ignore_index=True) if oos_trades else pd.DataFrame()
    params_seen = [tuple(sorted(f["params"].items())) for f in folds]
    return {
        "folds": folds,
        "oos": trade_metrics(all_oos),
        "oos_return_pct_sum": sum(f["test"]["net_return_pct"] for f in folds),
        "param_stability": (max(params_seen.count(p) for p in set(params_seen)) / len(params_seen)) if params_seen else None,
    }


def _deg(a: dict, b: dict) -> float | None:
    ea, eb = a["trades"].get("expectancy_r"), b["trades"].get("expectancy_r")
    if ea is None or eb is None:
        return None
    return eb - ea


def _warnings(train: dict, val: dict, test: dict) -> list[str]:
    w = []
    for name, rep in (("training", train), ("validazione", val), ("test", test)):
        if not rep["trades"].get("significant"):
            w.append(f"{name}: meno di 30 operazioni, risultati NON statisticamente significativi")
    et, ev = train["trades"].get("expectancy_r"), test["trades"].get("expectancy_r")
    if et is not None and ev is not None and et > 0 and ev < et * 0.5:
        w.append("forte degradazione dal training al test: possibile overfitting")
    if test["benchmark_buy_hold_return_pct"] is not None and test["net_return_pct"] < test["benchmark_buy_hold_return_pct"]:
        w.append("nel periodo di test la strategia rende meno del buy & hold")
    return w
