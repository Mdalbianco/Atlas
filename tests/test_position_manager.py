from atlas.domain import ExitReason
from atlas.engine.position_manager import ManagementParams, check_stop_target, on_bar_close
from atlas.strategy.trend_pullback import TrendPullback
from tests.factories import snap


def pos(**kw):
    base = dict(entry_price=100.0, initial_stop=96.0, stop_loss=96.0, take_profit=110.0, highest_price=100.0, bars_held=0, trailing_active=0, meta={})
    base.update(kw)
    return base


def test_stop_has_priority_over_target_in_same_bar():
    ex = check_stop_target(pos(), 100.0, 111.0, 95.0)
    assert ex.reason is ExitReason.STOP_LOSS and ex.reference_price == 96.0


def test_gap_below_stop_fills_at_open():
    ex = check_stop_target(pos(), 94.0, 95.0, 93.0)
    assert ex.reference_price == 94.0


def test_take_profit():
    ex = check_stop_target(pos(), 105.0, 111.0, 104.0)
    assert ex.reason is ExitReason.TAKE_PROFIT and ex.reference_price == 110.0
    assert check_stop_target(pos(), 101.0, 102.0, 99.0) is None


def test_trailing_stop_only_moves_up():
    p = pos()
    upd, ex = on_bar_close(p, snap(close=105.0, atr=1.0), 105.5, None, ManagementParams(1.0, 2.0, 48))
    assert ex is None and upd["stop_loss"] == 103.5 and upd["trailing_active"] == 1
    p.update(upd)
    upd2, _ = on_bar_close(p, snap(close=104.0, atr=1.0), 104.2, None, ManagementParams(1.0, 2.0, 48))
    assert "stop_loss" not in upd2  # non scende
    assert check_stop_target(p, 104, 104, 103.0).reason is ExitReason.TRAILING_STOP


def test_trailing_not_active_before_1r():
    upd, _ = on_bar_close(pos(), snap(close=102.0, atr=1.0), 103.0, None, ManagementParams())
    assert "stop_loss" not in upd


def test_time_stop_and_invalidation():
    upd, ex = on_bar_close(pos(bars_held=47), snap(close=101.0), 101.5, None, ManagementParams(time_stop_bars=48))
    assert ex.reason is ExitReason.TIME_STOP
    upd, ex = on_bar_close(pos(), snap(close=99.0, ema50=99.5, trend="laterale"), 100.0, TrendPullback(), ManagementParams())
    assert ex.reason is ExitReason.INVALIDATION


def test_breakeven_floor_is_net_of_costs():
    # dopo +1R con ATR ampio il pavimento è il pareggio NETTO (ingresso + costi A/R)
    upd, _ = on_bar_close(pos(), snap(close=104.5, atr=5.0), 104.5, None, ManagementParams(1.0, 2.5, 48, breakeven_cost_pct=1.0))
    assert upd["stop_loss"] == 101.0
