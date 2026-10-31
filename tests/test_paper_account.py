from datetime import datetime, timezone

import pytest

from atlas.domain import ExitReason, MarketRules, RiskDecision, ScoreResult, Signal
from atlas.engine.account import PaperAccount
from atlas.execution.paper import OrderRejected, PaperBroker
from atlas.risk.costs import CostModel
from atlas.storage.db import Database

RULES = MarketRules("BTC/EUR", amount_step=1e-8, min_cost=0.5)
COSTS = CostModel(0.4, 0.05, 0.1)


def make(tmp_path):
    db = Database(tmp_path / "t.db")
    return db, PaperAccount(db, PaperBroker(COSTS), 100.0)


def signal(bar=1):
    return Signal("BTC/EUR", "trend_pullback", "1.0.0", bar, 100.0, 96.0, 110.0, 2.0, ["motivo"], ["inval"])


def risk(qty=0.25):
    return RiskDecision(True, quantity=qty, cost=qty * 100, risk_amount=1.0, risk_pct=1.0, net_reward_risk=2.0)


SCORE = ScoreResult(70.0, "x", {}, {})


def test_open_and_close_accounting(tmp_path):
    db, acc = make(tmp_path)
    p = acc.open_position(signal(), risk(), SCORE, RULES, 100.0, None, {})
    buy_px = 100 * (1 + (0.05 + 0.05) / 100)
    assert p["entry_price"] == pytest.approx(buy_px)
    fee_in = 0.25 * buy_px * 0.004
    assert acc.cash == pytest.approx(100 - 0.25 * buy_px - fee_in)
    closed = acc.close_position(p, 110.0, ExitReason.TAKE_PROFIT)
    sell_px = 110 * (1 - 0.001)
    fee_out = 0.25 * sell_px * 0.004
    expected_pnl = 0.25 * sell_px - fee_out - (0.25 * buy_px + fee_in)
    assert closed["pnl"] == pytest.approx(expected_pnl)
    assert acc.cash == pytest.approx(100 + expected_pnl)
    assert closed["r_multiple"] > 0 and closed["status"] == "closed"
    assert db.get_state("consecutive_losses") == 0


def test_same_signal_never_executed_twice(tmp_path):
    db, acc = make(tmp_path)
    assert acc.open_position(signal(), risk(), SCORE, RULES, 100.0, None, {}) is not None
    assert acc.open_position(signal(), risk(), SCORE, RULES, 100.0, None, {}) is None
    assert len(db.query("SELECT * FROM orders")) == 1


def test_only_one_open_position_per_symbol(tmp_path):
    db, acc = make(tmp_path)
    acc.open_position(signal(1), risk(), SCORE, RULES, 100.0, None, {})
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        acc.open_position(signal(2), risk(), SCORE, RULES, 100.0, None, {})
    # la transazione fallita non deve aver toccato la liquidità
    assert len(db.open_positions()) == 1
    assert acc.cash == pytest.approx(100 - 0.25 * 100.1 * 1.004)


def test_double_close_is_ignored(tmp_path):
    _, acc = make(tmp_path)
    p = acc.open_position(signal(), risk(), SCORE, RULES, 100.0, None, {})
    assert acc.close_position(p, 95.0, ExitReason.STOP_LOSS) is not None
    cash = acc.cash
    assert acc.close_position(p, 95.0, ExitReason.STOP_LOSS) is None
    assert acc.cash == cash


def test_insufficient_cash_rejected(tmp_path):
    _, acc = make(tmp_path)
    with pytest.raises(OrderRejected):
        acc.open_position(signal(), risk(qty=2.0), SCORE, RULES, 100.0, None, {})


def test_state_survives_restart(tmp_path):
    db, acc = make(tmp_path)
    p = acc.open_position(signal(), risk(), SCORE, RULES, 100.0, None, {})
    acc.close_position(p, 95.0, ExitReason.STOP_LOSS)
    cash = acc.cash
    db.close()
    db2 = Database(tmp_path / "t.db")
    acc2 = PaperAccount(db2, PaperBroker(COSTS), 999.0)   # il capitale iniziale NON sovrascrive lo stato
    assert acc2.cash == pytest.approx(cash)
    assert db2.get_state("consecutive_losses") == 1
    assert len(db2.closed_positions()) == 1


def test_halt_and_pause(tmp_path):
    _, acc = make(tmp_path)
    acc.halt("prova")
    st = acc.state()
    assert st.halted and st.halt_reason == "prova"
    acc.clear_halt()
    acc.set_paused(True)
    st = acc.state()
    assert not st.halted and st.paused


def test_daily_rollover_uses_clock(tmp_path):
    db = Database(tmp_path / "c.db")
    clock = {"t": datetime(2026, 1, 1, 10, tzinfo=timezone.utc)}
    acc = PaperAccount(db, PaperBroker(COSTS), 100.0, clock=lambda: clock["t"])
    db.set_state("cash", 97.0)
    assert acc.state().daily_pnl_pct == pytest.approx(-3.0)
    clock["t"] = datetime(2026, 1, 2, 1, tzinfo=timezone.utc)
    assert acc.state().daily_pnl_pct == pytest.approx(0.0)
