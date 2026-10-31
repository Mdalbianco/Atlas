"""Validazione delle strategie su dati reali (walk-forward) e report di promozione.

Per OGNI strategia, presa singolarmente con lo stesso portafoglio virtuale da
100 € e gli stessi limiti di rischio:
1. walk-forward: ottimizzazione su una finestra di training (griglia piccola
   definita a priori nella strategia + soglia di score), test sulla finestra
   successiva mai vista, avanzamento della finestra;
2. aggregazione dei soli risultati FUORI CAMPIONE;
3. confronto con il buy & hold degli stessi periodi di test;
4. applicazione dei criteri di ``atlas.strategy.validation.CRITERIA``.

Il risultato è un report (JSON + Markdown). Lo stato "validata" diventa
effettivo solo se il file di stato viene aggiornato con ``--write-status`` e
committato da una persona.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from atlas.backtest.engine import Backtester, BacktestConfig
from atlas.backtest.metrics import full_report, max_drawdown, trade_metrics
from atlas.backtest.walkforward import _timeline, objective
from atlas.strategy.registry import STRATEGIES
from atlas.strategy.validation import CRITERIA, STATUS_FILE, evaluate_criteria


def _grid(name: str, base_scores=(60.0, 65.0, 70.0), override: dict | None = None) -> list[tuple[float, dict]]:
    cls = STRATEGIES[name]
    grid = dict(cls.param_grid())
    if override:
        unknown = set(override) - set(cls.default_params())
        if unknown:
            raise ValueError(f"Parametri sconosciuti per {name}: {', '.join(sorted(unknown))}")
        grid.update(override)
    combos: list[dict] = [{}]
    for key, values in grid.items():
        combos = [{**c, key: v} for c in combos for v in values]
    return [(ms, c) for ms in base_scores for c in combos]


def walk_forward_strategy(data, base: BacktestConfig, name: str, train_bars: int, test_bars: int, warmup_bars: int, min_trades: int, cache: dict, grid_override: dict | None = None) -> dict:
    tl = _timeline(data)
    folds, oos = [], []
    start = warmup_bars
    # l'ultimo periodo di test può essere più corto, purché lungo almeno metà del normale
    while start + train_bars + test_bars // 2 <= len(tl):
        tr = (tl[start], tl[start + train_bars])
        end = min(start + train_bars + test_bars, len(tl))
        te = (tl[start + train_bars], tl[end] if end < len(tl) else tl[-1] + 1)
        ranked = []
        for ms, params in _grid(name, override=grid_override):
            cfg = replace(base, min_score=ms)
            strat = STRATEGIES[name](costs=cfg.costs, **params)
            res = Backtester([strat], cfg).run(data, *tr, cache=cache)
            ranked.append((objective(res, min_trades), ms, params, res))
        ranked.sort(key=lambda x: x[0], reverse=True)
        best_obj, ms, params, train_res = ranked[0]
        cfg = replace(base, min_score=ms)
        test_res = Backtester([STRATEGIES[name](costs=cfg.costs, **params)], cfg).run(data, *te, cache=cache)
        rep = full_report(test_res)
        folds.append(
            {
                "train": [_iso(tr[0]), _iso(tr[1])],
                "test": [_iso(te[0]), _iso(te[1])],
                "params": {"min_score": ms, **params},
                "train_expectancy_r": trade_metrics(train_res.trades).get("expectancy_r"),
                "test_return_pct": rep["net_return_pct"],
                "test_trades": rep["trades"].get("trades", 0),
                "test_expectancy_r": rep["trades"].get("expectancy_r"),
                "test_max_dd_pct": rep["max_drawdown_pct"],
                "buy_hold_return_pct": rep["benchmark_buy_hold_return_pct"],
            }
        )
        if not test_res.trades.empty:
            oos.append(test_res.trades)
        start += test_bars
    oos_df = pd.concat(oos, ignore_index=True) if oos else pd.DataFrame()
    m = trade_metrics(oos_df)
    # curva fuori campione concatenata (ogni fold riparte da 100: si compongono i rendimenti)
    equity, curve = 100.0, [100.0]
    for f in folds:
        equity *= 1 + f["test_return_pct"] / 100
        curve.append(equity)
    max_dd = max([f["test_max_dd_pct"] for f in folds] + [max_drawdown(pd.Series(curve))[0]]) if folds else 0.0
    positive = sum(1 for f in folds if f["test_return_pct"] > 0) / len(folds) if folds else 0.0
    bh = 100.0
    for f in folds:
        bh *= 1 + (f["buy_hold_return_pct"] or 0) / 100
    passed, fails = evaluate_criteria(m, max_dd, positive)
    params_seen = [json.dumps(f["params"], sort_keys=True) for f in folds]
    stability = max(params_seen.count(p) for p in set(params_seen)) / len(params_seen) if params_seen else None
    return {
        "strategy": f"{name}@{STRATEGIES[name].version}",
        "status": "validata" if passed else "respinta",
        "configurations_tested": len(_grid(name, override=grid_override)),
        "grid": {"min_score": [60.0, 65.0, 70.0], **STRATEGIES[name].param_grid(), **(grid_override or {})},
        "reason": "tutti i criteri soddisfatti" if passed else "; ".join(fails),
        "folds": folds,
        "oos": m,
        "oos_return_pct": equity - 100,
        "buy_hold_return_pct": bh - 100,
        "max_drawdown_pct": max_dd,
        "positive_folds_ratio": positive,
        "param_stability": stability,
        "by_symbol": {k: trade_metrics(g) for k, g in oos_df.groupby("symbol")} if not oos_df.empty else {},
        "by_regime": {k: trade_metrics(g) for k, g in oos_df.groupby("regime")} if not oos_df.empty else {},
        "by_exit_reason": {k: trade_metrics(g) for k, g in oos_df.groupby("exit_reason")} if not oos_df.empty else {},
    }


def _iso(ms: int) -> str:
    return pd.to_datetime(ms, unit="ms", utc=True).isoformat()


def validate_all(data, base: BacktestConfig, names: list[str], train_bars=2000, test_bars=1000, warmup_bars=900, min_trades=10, source: str = "non specificata", grids: dict | None = None) -> dict:
    cache: dict = {}
    tl = _timeline(data)
    grids = grids or {}
    results = [walk_forward_strategy(data, base, n, train_bars, test_bars, warmup_bars, min_trades, cache, grids.get(n)) for n in names]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": {
            "symbols": list(data),
            "start": _iso(tl[0]),
            "end": _iso(tl[-1]),
            "bars": len(tl),
            "source": source,
        },
        "config": {
            "initial_capital": base.initial_capital,
            "fee_pct": base.costs.fee_pct,
            "slippage_pct": base.costs.slippage_pct,
            "spread_pct": base.spread_pct,
            "risk_per_trade_pct": base.limits.risk_per_trade_pct,
            "min_reward_risk": base.limits.min_reward_risk,
            "walk_forward": {"train_bars": train_bars, "test_bars": test_bars, "warmup_bars": warmup_bars},
        },
        "criteria": CRITERIA,
        "experiment": bool(grids),
        "results": results,
    }


def write_status(report: dict, path: Path = STATUS_FILE) -> None:
    strategies = {}
    for r in report["results"]:
        strategies[r["strategy"]] = {
            "status": r["status"],
            "reason": r["reason"],
            "validated_at": report["generated_at"],
            "data": report["data"],
            "oos": {k: r["oos"].get(k) for k in ("trades", "expectancy_r", "profit_factor", "win_rate", "net_pnl")},
            "oos_return_pct": r["oos_return_pct"],
            "buy_hold_return_pct": r["buy_hold_return_pct"],
            "max_drawdown_pct": r["max_drawdown_pct"],
            "positive_folds_ratio": r["positive_folds_ratio"],
        }
    path.write_text(json.dumps({"note": "Generato da `python -m atlas validate --write-status`; effettivo solo dopo commit.", "strategies": strategies}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def markdown(report: dict) -> str:
    def f(v, nd=2):
        return "n/d" if v is None else f"{v:.{nd}f}"

    d = report["data"]
    lines = [
        "# Report di validazione delle strategie" + (" — ESPERIMENTO (griglie modificate)" if report.get("experiment") else ""),
        "",
        f"Generato: {report['generated_at'][:19]} UTC  ",
        f"Dati: {', '.join(d['symbols'])} — {d['start'][:10]} → {d['end'][:10]} ({d['bars']} candele 1h)  ",
        f"Fonte: {d['source']}  ",
        f"Costi: commissione {report['config']['fee_pct']}% + slippage {report['config']['slippage_pct']}% per lato, spread {report['config']['spread_pct']}%  ",
        f"Walk-forward: training {report['config']['walk_forward']['train_bars']} candele, test {report['config']['walk_forward']['test_bars']} candele",
        "",
        "Tutti i numeri sotto sono **fuori campione** (periodi di test mai usati per scegliere i parametri).",
        "",
        "| Strategia | Esito | Operazioni | Win rate | Expectancy | Profit factor | Rendimento OOS | Buy & hold | Max DD | Fold positivi |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in report["results"]:
        o = r["oos"]
        lines.append(
            f"| {r['strategy']} | {'✅ validata' if r['status'] == 'validata' else '❌ respinta'} | {o.get('trades', 0)} | "
            f"{f(o.get('win_rate'), 0)}% | {f(o.get('expectancy_r'), 3)} R | {f(o.get('profit_factor'))} | "
            f"{f(r['oos_return_pct'])}% | {f(r['buy_hold_return_pct'])}% | {f(r['max_drawdown_pct'])}% | {r['positive_folds_ratio']:.0%} |"
        )
    lines += ["", "## Dettaglio", ""]
    for r in report["results"]:
        lines += [f"### {r['strategy']} — {r['status']}", "", f"Motivo: {r['reason']}", f"Configurazioni provate in ogni training: {r['configurations_tested']} (griglia {r['grid']})", f"Stabilità dei parametri tra i fold: {f(r['param_stability'])}", ""]
        lines += ["| Test | Parametri | Operazioni | Expectancy | Rendimento | Buy & hold |", "|---|---|---|---|---|---|"]
        for fo in r["folds"]:
            lines.append(f"| {fo['test'][0][:10]} → {fo['test'][1][:10]} | {fo['params']} | {fo['test_trades']} | {f(fo['test_expectancy_r'], 3)} R | {f(fo['test_return_pct'])}% | {f(fo['buy_hold_return_pct'])}% |")
        if r["by_regime"]:
            lines += ["", "Per regime: " + "; ".join(f"{k}: {m['trades']} op., {f(m['expectancy_r'], 2)} R" for k, m in r["by_regime"].items())]
        if r["by_symbol"]:
            lines += ["Per asset: " + "; ".join(f"{k}: {m['trades']} op., {f(m['expectancy_r'], 2)} R" for k, m in r["by_symbol"].items())]
        lines.append("")
    lines += [
        "## Criteri di promozione",
        "",
        *[f"- `{k}` = {v}" for k, v in report["criteria"].items()],
        "",
        "Una strategia respinta non entra nel portafoglio principale: continua a girare in un portafoglio ombra isolato "
        "per raccogliere evidenza. Nessun risultato passato garantisce risultati futuri.",
    ]
    return "\n".join(lines)
