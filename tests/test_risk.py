from datetime import datetime, timedelta, timezone

import pytest

from atlas.domain import MarketRules, Signal
from atlas.risk.costs import CostModel, net_reward_risk
from atlas.risk.manager import OpenPositionView, PortfolioState, RiskLimits, RiskManager

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
RULES = MarketRules("BTC/EUR", amount_step=1e-8, min_cost=0.5)


def sig(entry=100.0, stop=97.0, target=109.0, symbol="BTC/EUR"):
    return Signal(symbol, "test", "1", 0, entry, stop, target, atr=2.0)


def state(**kw):
    base = dict(cash=100.0, equity=100.0, peak_equity=100.0, day_start_equity=100.0)
    base.update(kw)
    return PortfolioState(**base)


def rm(**kw):
    return RiskManager(RiskLimits(**kw), CostModel(0.4, 0.05, 0.1))


def test_costs_can_turn_acceptable_gross_rr_into_rejection():
    # R/R lordo 2,67 ma netto < 1,8: rifiutato
    d = rm().evaluate(sig(target=108.0), state(), RULES, NOW)
    assert not d.approved and d.net_reward_risk < 1.8 < (108 - 100) / 3


def test_net_reward_risk_includes_costs():
    gross = (108 - 100) / (100 - 97)
    net, risk, reward = net_reward_risk(100, 97, 108, CostModel(0.4, 0.05, 0.1))
    assert net < gross
    assert risk > 3 and reward < 8
    assert net_reward_risk(100, 101, 108, CostModel())[0] == 0.0


def test_position_size_respects_risk_per_trade():
    d = rm().evaluate(sig(), state(), RULES, NOW)
    assert d.approved
    assert d.risk_amount == pytest.approx(1.0, rel=0.01)   # 1% di 100
    assert d.cost <= 50.0 + 1e-9                           # max 50% per posizione


def test_position_capped_by_max_position_and_cash():
    d = rm().evaluate(sig(stop=99.0, target=104.0), state(), RULES, NOW)  # stop stretto → quantità grande
    assert d.cost <= 50.0 + 1e-6
    d2 = rm().evaluate(sig(stop=99.0, target=104.0), state(cash=20.0), RULES, NOW)
    assert d2.cost <= 20.0


def test_rejects_low_reward_risk_regardless_of_everything():
    d = rm().evaluate(sig(target=103.0), state(), RULES, NOW)
    assert not d.approved and not d.checks["reward_risk"]


def test_rejects_when_costs_dominate_risk():
    d = rm(min_reward_risk=1.0).evaluate(sig(entry=100, stop=99.4, target=103), state(), RULES, NOW)
    assert not d.approved and not d.checks["costi"]


def test_rejects_below_min_order():
    d = rm(min_order_cost=60.0).evaluate(sig(), state(), RULES, NOW)
    assert not d.approved and not d.checks["minimi_ordine"]


def test_duplicate_and_max_positions():
    pos = OpenPositionView("BTC/EUR", 0.1, 100, 100, 97)
    d = rm().evaluate(sig(), state(positions=[pos]), RULES, NOW)
    assert not d.approved and not d.checks["nessun_duplicato"]
    two = [OpenPositionView("ETH/EUR", 0.1, 100, 100, 97), OpenPositionView("SOL/EUR", 0.1, 100, 100, 97)]
    d2 = rm().evaluate(sig(), state(positions=two, cash=60), RULES, NOW)
    assert not d2.approved and any("massimo di posizioni" in r for r in d2.reasons)


def test_daily_loss_and_drawdown_block():
    d = rm().evaluate(sig(), state(equity=96.5, cash=96.5, day_start_equity=100.0, peak_equity=100.0), RULES, NOW)
    assert not d.approved and any("giornaliera" in r for r in d.reasons)
    d2 = rm().evaluate(sig(), state(equity=84.0, cash=84.0, day_start_equity=84.0, peak_equity=100.0), RULES, NOW)
    assert not d2.approved and any("drawdown" in r for r in d2.reasons)
    assert rm().should_halt(state(equity=84.0, peak_equity=100.0)) is not None


def test_consecutive_losses_cooldown():
    st = state(consecutive_losses=4, last_loss_at=NOW - timedelta(hours=2))
    assert not rm().evaluate(sig(), st, RULES, NOW).approved
    st2 = state(consecutive_losses=4, last_loss_at=NOW - timedelta(hours=30))
    assert rm().evaluate(sig(), st2, RULES, NOW).approved


def test_pause_and_halt_block():
    assert not rm().evaluate(sig(), state(paused=True), RULES, NOW).approved
    assert not rm().evaluate(sig(), state(halted=True, halt_reason="x"), RULES, NOW).approved


def test_spread_block():
    d = rm().evaluate(sig(), state(), RULES, NOW, spread_pct=0.9)
    assert not d.approved and not d.checks["spread"]


def test_correlated_exposure_limited():
    open_pos = OpenPositionView("ETH/EUR", 0.4, 100, 100, 97)  # rischio aperto 1.2
    d = rm(max_correlated_risk_pct=1.5).evaluate(sig(), state(positions=[open_pos], cash=60), RULES, NOW, correlations={"ETH/EUR": 0.9})
    assert d.approved and d.risk_amount <= 0.31
    d2 = rm(max_correlated_risk_pct=1.0).evaluate(sig(), state(positions=[open_pos], cash=60), RULES, NOW, correlations={"ETH/EUR": 0.9})
    assert not d2.approved
    d3 = rm().evaluate(sig(), state(positions=[open_pos], cash=60), RULES, NOW, correlations={"ETH/EUR": 0.2})
    assert d3.approved and d3.risk_amount == pytest.approx(1.0, rel=0.02)


def test_invalid_levels():
    assert not rm().evaluate(sig(stop=101), state(), RULES, NOW).approved


def test_quantity_rounded_to_step():
    rules = MarketRules("BTC/EUR", amount_step=0.001, min_cost=0.5)
    d = rm().evaluate(sig(), state(), rules, NOW)
    assert abs(d.quantity / 0.001 - round(d.quantity / 0.001)) < 1e-6


def test_target_for_net_r_is_inverse_of_net_rr():
    from atlas.risk.costs import target_for_net_r

    c = CostModel(0.4, 0.05, 0.1)
    for stop in (99.0, 98.0, 96.0):
        tgt = target_for_net_r(100.0, stop, 2.0, c)
        assert net_reward_risk(100.0, stop, tgt, c)[0] == pytest.approx(2.0, rel=1e-9)
    # stop più stretto → target più lontano in termini di R lordi
    gross = lambda stop: (target_for_net_r(100, stop, 2.0, c) - 100) / (100 - stop)
    assert gross(99.0) > gross(96.0) > 2.0
