"""Il paper trading live e il backtest devono prendere le stesse decisioni sugli stessi dati.

Il mercato sintetico viene "riprodotto" candela per candela (la candela in formazione mostra solo
l'apertura); il ciclo live gira 1 minuto dopo ogni apertura. Gli ingressi devono coincidere.
"""

from dataclasses import replace

import pandas as pd
import pytest

from atlas.app import Atlas
from atlas.backtest.engine import Backtester, BacktestConfig
from atlas.data.sources import SyntheticMarket
from atlas.engine.position_manager import ManagementParams
from atlas.risk.costs import CostModel
from atlas.strategy.registry import build_strategies
from atlas.telegram.notifier import NullNotifier
from tests.conftest import Clock


def test_live_and_backtest_take_the_same_trades(settings):
    m = SyntheticMarket(bars=2000, seed=7)
    ts = m.data["BTC/EUR"].timestamp.tolist()
    start = 1700
    s = replace(settings, watchlist=tuple(m.data), candles_limit=720)
    clock = Clock(0)
    atlas = Atlas(s, source=m, notifier=NullNotifier(), clock=clock)
    for t in ts[start:]:
        m.now_ms = t
        clock.ms = t + 60_000
        assert atlas.cycle.run_once().ok
    live = pd.DataFrame(atlas.db.query("SELECT * FROM positions"))

    costs = CostModel(s.taker_fee_pct, s.slippage_pct, m.spread_pct)
    cfg = BacktestConfig(market_symbol="BTC/EUR", spread_pct=m.spread_pct, costs=costs,
                         management=ManagementParams(breakeven_cost_pct=2 * costs.per_side_pct))
    bt = Backtester(build_strategies(s.strategies, costs=costs), cfg).run(m.data, start_ts=ts[start])
    if bt.trades.empty and live.empty:
        pytest.skip("nessuna operazione nel campione")
    live_entries = sorted(zip(live.symbol, live.signal_bar_ts + 3_600_000))
    bt_entries = sorted(zip(bt.trades.symbol, bt.trades.entry_ts))
    # le operazioni chiuse forzatamente a fine backtest restano aperte nel live: confrontiamo gli ingressi
    assert live_entries == bt_entries
