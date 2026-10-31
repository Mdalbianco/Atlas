"""Backtester event-driven multi-asset con portafoglio condiviso.

Usa ESATTAMENTE gli stessi componenti del paper trading (snapshot, strategie,
scoring, risk manager, regole di gestione posizione, modello costi).

Regole anti-bias:
- la decisione si prende sulla CHIUSURA della candela ``i`` usando solo dati
  ``<= i``; l'esecuzione avviene all'APERTURA della candela ``i+1``;
- il timeframe superiore usa solo candele già chiuse all'istante della decisione;
- se stop e target sono toccati nella stessa candela si assume lo stop;
- costi (commissioni, spread, slippage) applicati a ogni esecuzione;
- la finestra di trading [start, end) può essere ristretta lasciando lo storico
  precedente solo come riscaldamento degli indicatori (walk-forward).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from atlas.analysis.indicators import ArrayFrame, add_indicators
from atlas.analysis.snapshot import MIN_BARS, MarketContext, Snapshot, build_snapshot
from atlas.data.market_data import timeframe_ms
from atlas.data.sources import resample
from atlas.domain import ExitReason, MarketRules
from atlas.engine.decision import DecisionEngine
from atlas.engine.position_manager import ManagementParams, check_stop_target, on_bar_close
from atlas.risk.costs import CostModel
from atlas.risk.manager import OpenPositionView, PortfolioState, RiskLimits, RiskManager
from atlas.scoring import ScoreEngine
from atlas.strategy.base import Strategy


@dataclass
class BacktestConfig:
    initial_capital: float = 100.0
    timeframe: str = "1h"
    higher_timeframe: str = "4h"
    min_score: float = 65.0
    spread_pct: float = 0.10
    costs: CostModel = field(default_factory=CostModel)
    limits: RiskLimits = field(default_factory=RiskLimits)
    management: ManagementParams = field(default_factory=ManagementParams)
    market_symbol: str | None = None
    rules: dict[str, MarketRules] = field(default_factory=dict)


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    equity: pd.DataFrame          # timestamp, equity, cash, exposure
    decisions: dict[str, int]
    config: BacktestConfig
    symbols: list[str]
    start_ts: int
    end_ts: int
    benchmark_equity: pd.Series | None = None


def _dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


class Backtester:
    def __init__(self, strategies: list[Strategy], config: BacktestConfig) -> None:
        self.cfg = config
        self.strategies = {s.name: s for s in strategies}
        self.risk = RiskManager(config.limits, config.costs)
        self.engine = DecisionEngine(strategies, ScoreEngine(config.costs, config.limits.min_reward_risk), self.risk, config.min_score)

    # ------------------------------------------------------------------
    def _prepare(self, data: dict[str, pd.DataFrame]):
        cfg = self.cfg
        tf, htf = timeframe_ms(cfg.timeframe), timeframe_ms(cfg.higher_timeframe)
        prepared = {}
        for sym, df in data.items():
            df = df.sort_values("timestamp").reset_index(drop=True)
            hdf = resample(df, cfg.higher_timeframe)
            enr, henr = add_indicators(df), add_indicators(hdf)
            close_time = df["timestamp"].to_numpy() + tf
            # indice dell'ultima candela superiore chiusa entro la chiusura della candela primaria
            h_close = hdf["timestamp"].to_numpy() + htf
            h_idx = np.searchsorted(h_close, close_time, side="right") - 1
            prepared[sym] = {"df": df, "enr": ArrayFrame.from_frame(enr), "henr": ArrayFrame.from_frame(henr), "h_idx": h_idx, "pos": {int(t): i for i, t in enumerate(df["timestamp"])}}
        return prepared

    def _snapshot(self, cache: dict, key, sym: str, tfname: str, enr: ArrayFrame, i: int) -> Snapshot | None:
        if i + 1 < MIN_BARS:
            return None
        k = (sym, tfname, i)
        if k not in cache:
            if len(cache) > 200_000:
                cache.clear()
            view = enr.upto(i + 1)
            cache[k] = build_snapshot(sym, tfname, view, enriched=view)
        return cache[k]

    def run(self, data: dict[str, pd.DataFrame], start_ts: int | None = None, end_ts: int | None = None, cache: dict | None = None) -> BacktestResult:
        """Esegue il backtest. ``cache`` (facoltativa) condivide indicatori e snapshot
        tra più esecuzioni sugli stessi dati: non dipendono dai parametri delle strategie."""
        cfg = self.cfg
        if cache is not None and cache.get("key") == (id(data), cfg.timeframe, cfg.higher_timeframe):
            prep = cache["prep"]
        else:
            prep = self._prepare(data)
            if cache is not None:
                cache.clear()
                cache.update({"key": (id(data), cfg.timeframe, cfg.higher_timeframe), "prep": prep, "snaps": {}})
        timeline = sorted(set().union(*[set(p["df"]["timestamp"].astype("int64")) for p in prep.values()]))
        start_ts = start_ts if start_ts is not None else timeline[0]
        end_ts = end_ts if end_ts is not None else timeline[-1] + 1
        tf = timeframe_ms(cfg.timeframe)

        cash = cfg.initial_capital
        peak = cash
        day, day_start = None, cash
        consecutive_losses, last_loss_at = 0, None
        positions: dict[str, dict] = {}
        pending_entries: dict[str, tuple] = {}
        pending_exits: dict[str, tuple] = {}
        trades: list[dict] = []
        equity_rows: list[tuple] = []
        decisions = {"ENTER": 0, "SKIP": 0}
        hcache: dict = cache["snaps"] if cache is not None else {}
        last_close: dict[str, float] = {}

        def close_pos(sym: str, ref_price: float, reason: ExitReason, detail: str, ts: int) -> None:
            nonlocal cash, consecutive_losses, last_loss_at
            pos = positions.pop(sym)
            px = cfg.costs.with_spread(cfg.spread_pct).exit_price(ref_price)
            proceeds = px * pos["quantity"]
            fee = cfg.costs.fee(proceeds)
            cash += proceeds - fee
            entry_total = pos["entry_price"] * pos["quantity"] + pos["entry_fee"]
            pnl = proceeds - fee - entry_total
            init_risk = (pos["entry_price"] - pos["initial_stop"]) * pos["quantity"] + pos["entry_fee"]
            if pnl < 0:
                consecutive_losses += 1
                last_loss_at = _dt(ts)
            else:
                consecutive_losses = 0
            trades.append(
                {
                    "symbol": sym,
                    "strategy": pos["strategy"],
                    "entry_ts": pos["entry_ts"],
                    "exit_ts": ts,
                    "entry_price": pos["entry_price"],
                    "exit_price": px,
                    "quantity": pos["quantity"],
                    "fees": pos["entry_fee"] + fee,
                    "pnl": pnl,
                    "pnl_pct": pnl / entry_total * 100,
                    "r_multiple": pnl / init_risk if init_risk > 0 else 0.0,
                    "exit_reason": reason.value,
                    "score": pos["score"],
                    "regime": pos["regime"],
                    "bars_held": pos["bars_held"],
                    "expected_rr": pos["expected_rr"],
                }
            )

        for ts in timeline:
            if ts >= end_ts:
                break
            in_window = ts >= start_ts
            now = _dt(ts + tf)
            # 1) esecuzione all'apertura delle operazioni decise alla candela precedente
            for sym in list(pending_exits):
                p = prep[sym]
                i = p["pos"].get(ts)
                if i is None:
                    continue
                reason, detail = pending_exits.pop(sym)
                if sym in positions:
                    close_pos(sym, float(p["df"]["open"].iloc[i]), reason, detail, ts)
            for sym in list(pending_entries):
                p = prep[sym]
                i = p["pos"].get(ts)
                if i is None:
                    continue
                signal, risk, score, regime = pending_entries.pop(sym)
                if sym in positions:
                    continue
                open_px = float(p["df"]["open"].iloc[i])
                # gap oltre lo stop all'apertura: il segnale non è più valido
                if open_px <= signal.stop_loss or open_px >= signal.take_profit:
                    continue
                px = cfg.costs.with_spread(cfg.spread_pct).entry_price(open_px)
                qty = risk.quantity
                cost = qty * px
                fee = cfg.costs.fee(cost)
                if cost + fee > cash:
                    qty = (cash / (1 + cfg.costs.fee_pct / 100)) / px
                    cost, fee = qty * px, cfg.costs.fee(qty * px)
                if qty <= 0:
                    continue
                cash -= cost + fee
                positions[sym] = {
                    "strategy": signal.strategy,
                    "entry_ts": ts,
                    "entry_price": px,
                    "quantity": qty,
                    "entry_fee": fee,
                    "initial_stop": signal.stop_loss,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "highest_price": px,
                    "bars_held": 0,
                    "trailing_active": 0,
                    "meta": dict(signal.meta),
                    "score": score.score,
                    "regime": regime,
                    "expected_rr": risk.net_reward_risk,
                }

            # 2) gestione intrabar e a chiusura delle posizioni aperte
            for sym in list(positions):
                p = prep[sym]
                i = p["pos"].get(ts)
                if i is None:
                    continue
                row = p["df"].iloc[i]
                pos = positions[sym]
                ex = check_stop_target(pos, float(row.open), float(row.high), float(row.low))
                if ex:
                    pos["bars_held"] += 1
                    close_pos(sym, ex.reference_price, ex.reason, ex.detail, ts)
                    continue
                snap = self._snapshot(hcache, None, sym, cfg.timeframe, p["enr"], i)
                if snap is None:
                    continue
                updates, ex = on_bar_close(pos, snap, float(row.high), self.strategies.get(pos["strategy"]), cfg.management)
                pos.update(updates)
                if ex:
                    pending_exits[sym] = (ex.reason, ex.detail)

            # 3) mark-to-market
            for sym, p in prep.items():
                i = p["pos"].get(ts)
                if i is not None:
                    last_close[sym] = float(p["df"]["close"].iloc[i])
            exposure = sum(pos["quantity"] * last_close.get(s, pos["entry_price"]) for s, pos in positions.items())
            equity = cash + exposure
            peak = max(peak, equity)
            if day != now.date():
                day, day_start = now.date(), equity
            if in_window:
                equity_rows.append((ts, equity, cash, exposure))

            # 4) nuove decisioni alla chiusura
            if not in_window:
                continue
            state = PortfolioState(
                cash=cash,
                equity=equity,
                peak_equity=peak,
                day_start_equity=day_start,
                positions=[
                    OpenPositionView(s, pp["quantity"], pp["entry_price"], last_close.get(s, pp["entry_price"]), pp["stop_loss"])
                    for s, pp in positions.items()
                ],
                consecutive_losses=consecutive_losses,
                last_loss_at=last_loss_at,
            )
            if self.risk.portfolio_blocks(state, now):
                continue
            market_snap = None
            if cfg.market_symbol and cfg.market_symbol in prep:
                mp = prep[cfg.market_symbol]
                mi = mp["pos"].get(ts)
                if mi is not None:
                    hi = int(mp["h_idx"][mi])
                    market_snap = self._snapshot(hcache, None, cfg.market_symbol, cfg.higher_timeframe, mp["henr"], hi) if hi >= 0 else None
            for sym, p in prep.items():
                if sym in positions or sym in pending_entries:
                    continue
                i = p["pos"].get(ts)
                if i is None:
                    continue
                snap = self._snapshot(hcache, None, sym, cfg.timeframe, p["enr"], i)
                hi = int(p["h_idx"][i])
                hsnap = self._snapshot(hcache, None, sym, cfg.higher_timeframe, p["henr"], hi) if hi >= 0 else None
                if snap is None or hsnap is None:
                    continue
                ctx = MarketContext(sym, snap, hsnap, market=market_snap, spread_pct=cfg.spread_pct)
                rules = cfg.rules.get(sym, MarketRules(sym, min_cost=0.5))
                corr = self._correlations(prep, sym, list(positions), i, ts)
                d = self.engine.decide_entry(ctx, state, rules, now, correlations=corr)
                decisions[d.action.value] = decisions.get(d.action.value, 0) + 1
                if d.action.value == "ENTER":
                    pending_entries[sym] = (d.signal, d.risk, d.score, snap.regime)
                    # aggiorna lo stato per le decisioni successive nello stesso istante
                    state.positions.append(OpenPositionView(sym, d.risk.quantity, d.signal.entry_price, d.signal.entry_price, d.signal.stop_loss))
                    state.cash -= d.risk.cost

        # chiusura forzata a fine finestra
        last_ts = equity_rows[-1][0] if equity_rows else end_ts
        for sym in list(positions):
            close_pos(sym, last_close.get(sym, positions[sym]["entry_price"]), ExitReason.END_OF_DATA, "fine del periodo di test", last_ts)
        if equity_rows:
            equity_rows[-1] = (last_ts, cash, cash, 0.0)

        equity_df = pd.DataFrame(equity_rows, columns=["timestamp", "equity", "cash", "exposure"])
        trades_df = pd.DataFrame(trades)
        bench = self._buy_and_hold(prep, equity_df)
        return BacktestResult(trades_df, equity_df, decisions, cfg, list(data), int(start_ts), int(last_ts), bench)

    # ------------------------------------------------------------------
    @staticmethod
    def _correlations(prep: dict, sym: str, open_syms: list[str], i: int, ts: int, window: int = 168) -> dict[str, float]:
        out = {}
        if not open_syms:
            return out
        a = prep[sym]["df"]["close"].iloc[max(0, i - window) : i + 1].pct_change().dropna().to_numpy()
        for other in open_syms:
            j = prep[other]["pos"].get(ts)
            if j is None:
                continue
            b = prep[other]["df"]["close"].iloc[max(0, j - window) : j + 1].pct_change().dropna().to_numpy()
            n = min(len(a), len(b))
            if n > 20:
                out[other] = float(np.corrcoef(a[-n:], b[-n:])[0, 1])
        return out

    def _buy_and_hold(self, prep: dict, equity_df: pd.DataFrame) -> pd.Series | None:
        """Benchmark: capitale diviso in parti uguali e comprato all'inizio della finestra (costi inclusi)."""
        if equity_df.empty:
            return None
        cfg = self.cfg
        c = cfg.costs.with_spread(cfg.spread_pct)
        start = int(equity_df["timestamp"].iloc[0])
        alloc = cfg.initial_capital / len(prep)
        series = []
        for sym, p in prep.items():
            df = p["df"].set_index("timestamp")["close"]
            df = df[df.index >= start]
            if df.empty:
                continue
            qty = alloc / (1 + c.fee_pct / 100) / c.entry_price(float(df.iloc[0]))
            value = df.apply(lambda x: c.exit_price(x) * qty * (1 - c.fee_pct / 100))
            series.append(value)
        if not series:
            return None
        total = pd.concat(series, axis=1).ffill().sum(axis=1)
        return total.reindex(equity_df["timestamp"].to_numpy()).ffill()
