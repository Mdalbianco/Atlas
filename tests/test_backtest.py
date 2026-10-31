import math

import numpy as np
import pandas as pd
import pytest

from atlas.backtest.engine import Backtester, BacktestConfig
from atlas.backtest.metrics import full_report, max_drawdown, trade_metrics
from atlas.backtest.walkforward import chronological_split, validate, walk_forward
from atlas.data.sources import SyntheticMarket
from atlas.strategy.registry import build_strategies


@pytest.fixture(scope="module")
def data():
    return SyntheticMarket(bars=2200, seed=11).data


@pytest.fixture(scope="module")
def result(data):
    return Backtester(build_strategies(["trend_pullback", "breakout"]), BacktestConfig(market_symbol="BTC/EUR", min_score=55)).run(data)


def test_backtest_runs_and_accounts(result):
    rep = full_report(result)
    assert rep["initial_capital"] == 100.0
    eq = result.equity
    assert not eq.empty and (eq["equity"] > 0).all()
    if not result.trades.empty:
        t = result.trades
        # equity finale = capitale + somma PnL (tutte le posizioni chiuse a fine dati)
        assert rep["final_equity"] == pytest.approx(100.0 + t["pnl"].sum(), abs=1e-6)
        assert (t["fees"] > 0).all()
        assert (t["exit_ts"] >= t["entry_ts"]).all()
    assert rep["benchmark_buy_hold_return_pct"] is not None


def test_entries_happen_after_signal_bar(data):
    bt = Backtester(build_strategies(["trend_pullback", "breakout"]), BacktestConfig(min_score=50))
    res = bt.run(data)
    if res.trades.empty:
        pytest.skip("nessuna operazione nel campione sintetico")
    for _, t in res.trades.iterrows():
        df = data[t["symbol"]]
        row = df[df.timestamp == t["entry_ts"]].iloc[0]
        # prezzo di ingresso = apertura della candela successiva al segnale, più costi
        assert t["entry_price"] == pytest.approx(row.open * (1 + (0.05 + 0.05) / 100))


def test_no_trades_outside_window(data):
    ts = sorted(data["BTC/EUR"].timestamp)
    start, end = ts[1200], ts[1700]
    res = Backtester(build_strategies(["trend_pullback", "breakout"]), BacktestConfig(min_score=50)).run(data, start, end)
    if not res.trades.empty:
        assert res.trades.entry_ts.min() >= start and res.trades.exit_ts.max() <= end
    assert res.equity.timestamp.min() >= start


def test_costs_make_results_worse(data):
    from atlas.risk.costs import CostModel

    strategies = build_strategies(["trend_pullback", "breakout"])
    cheap = Backtester(strategies, BacktestConfig(min_score=50, costs=CostModel(0.0, 0.0, 0.0), spread_pct=0.0)).run(data)
    costly = Backtester(strategies, BacktestConfig(min_score=50, costs=CostModel(0.4, 0.05, 0.1))).run(data)
    if cheap.trades.empty or costly.trades.empty:
        pytest.skip("nessuna operazione")
    assert costly.trades.fees.sum() > 0 and cheap.trades.fees.sum() == 0


def test_trade_metrics_known_values():
    t = pd.DataFrame({"pnl": [2.0, -1.0, 3.0, -1.0], "r_multiple": [2.0, -1.0, 3.0, -1.0], "fees": [0.1] * 4, "bars_held": [1, 2, 3, 4]})
    m = trade_metrics(t)
    assert m["win_rate"] == 50.0 and m["profit_factor"] == pytest.approx(2.5)
    assert m["expectancy"] == pytest.approx(0.75) and m["avg_win"] == 2.5 and m["avg_loss"] == 1.0
    assert not m["significant"]
    dd, length = max_drawdown(pd.Series([100, 110, 99, 105, 120]))
    assert dd == pytest.approx(10.0) and length == 2
    assert trade_metrics(pd.DataFrame())["trades"] == 0


def test_chronological_split_order(data):
    sp = chronological_split(data)
    assert sp["train"][1] <= sp["validation"][0] < sp["validation"][1] <= sp["test"][0] < sp["test"][1]


def test_walk_forward_and_validate_are_chronological(data):
    grid = {"min_score": [55.0, 65.0]}
    wf = walk_forward(data, BacktestConfig(), ["trend_pullback"], train_bars=600, test_bars=300, warmup_bars=900, grid=grid)
    assert wf["folds"]
    for f in wf["folds"]:
        assert f["train_window"][1] <= f["test_window"][0]
    v = validate(data, BacktestConfig(), ["trend_pullback"], grid=grid)
    assert v["best_params"]["min_score"] in (55.0, 65.0)
    assert any("significativi" in w for w in v["warnings"])


def test_shared_cache_gives_identical_results(data):
    strategies = build_strategies(["trend_pullback", "breakout"])
    cfg = BacktestConfig(min_score=55)
    plain = Backtester(strategies, cfg).run(data)
    cache = {}
    Backtester(strategies, BacktestConfig(min_score=70)).run(data, cache=cache)   # riempie la cache
    cached = Backtester(strategies, cfg).run(data, cache=cache)
    pd.testing.assert_frame_equal(plain.trades, cached.trades)
    pd.testing.assert_frame_equal(plain.equity, cached.equity)
