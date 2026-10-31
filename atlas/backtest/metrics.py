"""Metriche di performance per backtest e paper trading."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

MIN_TRADES_FOR_SIGNIFICANCE = 30


def max_drawdown(equity: pd.Series) -> tuple[float, int]:
    """Drawdown massimo in % e durata massima (in campioni) sotto il picco."""
    if equity.empty:
        return 0.0, 0
    peak = equity.cummax()
    dd = (equity - peak) / peak * 100
    underwater = (dd < 0).astype(int).to_numpy()
    longest = cur = 0
    for u in underwater:
        cur = cur + 1 if u else 0
        longest = max(longest, cur)
    return max(0.0, float(-dd.min())), longest


def trade_metrics(trades: pd.DataFrame) -> dict:
    if trades is None or trades.empty:
        return {"trades": 0}
    pnl = trades["pnl"]
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    gross_win, gross_loss = float(wins.sum()), float(-losses.sum())
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(-losses.mean()) if len(losses) else 0.0
    return {
        "trades": int(len(trades)),
        "win_rate": float(len(wins) / len(trades) * 100),
        "net_pnl": float(pnl.sum()),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else (math.inf if gross_win > 0 else 0.0),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "win_loss_ratio": float(avg_win / avg_loss) if avg_loss > 0 else math.inf if avg_win > 0 else 0.0,
        "expectancy": float(pnl.mean()),
        "expectancy_r": float(trades["r_multiple"].mean()) if "r_multiple" in trades else None,
        "total_fees": float(trades["fees"].sum()) if "fees" in trades else 0.0,
        "avg_bars_held": float(trades["bars_held"].mean()) if "bars_held" in trades else None,
        "significant": bool(len(trades) >= MIN_TRADES_FOR_SIGNIFICANCE),
    }


def sharpe_ratio(equity: pd.Series, periods_per_year: float) -> float | None:
    rets = equity.pct_change().dropna()
    if len(rets) < 30 or rets.std() == 0:
        return None
    return float(rets.mean() / rets.std() * math.sqrt(periods_per_year))


def group_metrics(trades: pd.DataFrame, column: str) -> dict[str, dict]:
    if trades is None or trades.empty or column not in trades:
        return {}
    return {str(k): trade_metrics(g) for k, g in trades.groupby(column)}


def score_buckets(trades: pd.DataFrame, edges: tuple[float, ...] = (0, 55, 65, 75, 101)) -> dict[str, dict]:
    if trades is None or trades.empty:
        return {}
    labels = [f"{int(a)}-{int(b) - 1}" for a, b in zip(edges[:-1], edges[1:])]
    buckets = pd.cut(trades["score"], bins=list(edges), labels=labels, right=False)
    return {str(k): trade_metrics(g) for k, g in trades.groupby(buckets, observed=True)}


def full_report(result, periods_per_year: float = 24 * 365) -> dict:
    eq = result.equity.set_index("timestamp")["equity"] if not result.equity.empty else pd.Series(dtype=float)
    initial = result.config.initial_capital
    final = float(eq.iloc[-1]) if len(eq) else initial
    dd, dd_len = max_drawdown(eq)
    tm = trade_metrics(result.trades)
    exposure_time = float((result.equity["exposure"] > 0).mean() * 100) if not result.equity.empty else 0.0
    bench = result.benchmark_equity
    bench_return = float(bench.iloc[-1] / initial * 100 - 100) if bench is not None and len(bench) else None
    bench_dd = max_drawdown(bench.dropna())[0] if bench is not None and len(bench) else None
    return {
        "period": {
            "start": pd.to_datetime(result.start_ts, unit="ms", utc=True).isoformat(),
            "end": pd.to_datetime(result.end_ts, unit="ms", utc=True).isoformat(),
            "bars": int(len(eq)),
            "symbols": result.symbols,
        },
        "initial_capital": initial,
        "final_equity": final,
        "net_return_pct": final / initial * 100 - 100,
        "max_drawdown_pct": dd,
        "max_drawdown_bars": dd_len,
        "sharpe": sharpe_ratio(eq, periods_per_year) if tm.get("significant") else None,
        "exposure_time_pct": exposure_time,
        "trades": tm,
        "by_symbol": group_metrics(result.trades, "symbol"),
        "by_strategy": group_metrics(result.trades, "strategy"),
        "by_regime": group_metrics(result.trades, "regime"),
        "by_exit_reason": group_metrics(result.trades, "exit_reason"),
        "by_score": score_buckets(result.trades),
        "decisions": result.decisions,
        "benchmark_buy_hold_return_pct": bench_return,
        "benchmark_buy_hold_max_dd_pct": bench_dd,
    }


def _fmt(v, nd=2) -> str:
    if v is None:
        return "n/d"
    if isinstance(v, float):
        if math.isinf(v):
            return "∞"
        return f"{v:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(v)


def format_report(rep: dict) -> str:
    t = rep["trades"]
    lines = [
        f"Periodo: {rep['period']['start'][:16]} → {rep['period']['end'][:16]} ({rep['period']['bars']} candele)",
        f"Asset: {', '.join(rep['period']['symbols'])}",
        f"Capitale: {_fmt(rep['initial_capital'])} → {_fmt(rep['final_equity'])}  ({_fmt(rep['net_return_pct'])}%)",
        f"Buy & hold (benchmark): {_fmt(rep['benchmark_buy_hold_return_pct'])}%  (drawdown {_fmt(rep['benchmark_buy_hold_max_dd_pct'])}%)",
        f"Drawdown massimo: {_fmt(rep['max_drawdown_pct'])}%",
        f"Tempo investito: {_fmt(rep['exposure_time_pct'])}%",
        f"Operazioni: {t.get('trades', 0)}",
    ]
    if t.get("trades"):
        lines += [
            f"Win rate: {_fmt(t['win_rate'])}%   Profit factor: {_fmt(t['profit_factor'])}",
            f"Media vincite/perdite: {_fmt(t['avg_win'])} / {_fmt(t['avg_loss'])}  (rapporto {_fmt(t['win_loss_ratio'])})",
            f"Expectancy: {_fmt(t['expectancy'], 3)} per operazione ({_fmt(t['expectancy_r'])} R)",
            f"Costi totali: {_fmt(t['total_fees'])}",
            f"Sharpe: {_fmt(rep['sharpe'])}" + ("" if t["significant"] else f"  (non calcolato: meno di {MIN_TRADES_FOR_SIGNIFICANCE} operazioni)"),
        ]
        for title, key in (("Per strategia", "by_strategy"), ("Per asset", "by_symbol"), ("Per regime", "by_regime"), ("Per fascia di score", "by_score"), ("Per motivo di uscita", "by_exit_reason")):
            lines.append(f"{title}:")
            for k, m in rep[key].items():
                lines.append(f"  {k}: {m['trades']} op., win {_fmt(m['win_rate'], 0)}%, PnL {_fmt(m['net_pnl'])}, exp {_fmt(m['expectancy_r'])}R")
    return "\n".join(lines)
