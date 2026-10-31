import pytest

from atlas.domain import Signal
from atlas.risk.costs import CostModel
from atlas.scoring import DEFAULT_WEIGHTS, ScoreEngine, classify
from atlas.strategy.breakout import VolumeBreakout
from atlas.strategy.registry import STRATEGIES, build_strategies, describe
from atlas.strategy.trend_pullback import TrendPullback
from tests.factories import ctx, snap, structure


def test_trend_pullback_signal_on_ideal_setup():
    ev = TrendPullback().evaluate(ctx())
    assert ev.signal is not None
    s = ev.signal
    assert s.stop_loss < s.entry_price < s.take_profit
    assert 1.0 * 2.0 <= s.entry_price - s.stop_loss <= 3 * 2.0 + 1e-9   # tra 1 e 3 ATR
    assert s.invalidation and s.reasons


@pytest.mark.parametrize(
    "override,fragment",
    [
        ({"trend": "ribassista"}, "trend"),
        ({"adx": 10.0}, "ADX"),
        ({"rsi": 80.0}, "RSI"),
        ({"macd_hist": 0.05, "macd_hist_prev": 0.1}, "momentum"),
    ],
)
def test_trend_pullback_rejections_are_explained(override, fragment):
    ev = TrendPullback().evaluate(ctx(snap(**override)))
    assert ev.signal is None
    assert any(fragment in r for r in ev.reasons)


def test_trend_pullback_needs_higher_tf():
    ev = TrendPullback().evaluate(ctx(higher=snap(timeframe="4h", trend="ribassista")))
    assert ev.signal is None


def test_target_capped_below_strong_resistance():
    st = structure(nearest_resistance=104.0, resistance_strength=3, dist_resistance_atr=2.0)
    ev = TrendPullback().evaluate(ctx(snap(structure=st)))
    assert ev.signal.take_profit < 104.0


def test_breakout_signal_and_false_breakout_invalidation():
    st = structure(breakout=True, breakout_level=99.0, range_atr=4.0, pullback_to_ema=False)
    p = snap(structure=st, rel_volume=2.0, rsi=62.0)
    ev = VolumeBreakout().evaluate(ctx(p))
    assert ev.signal is not None and ev.signal.meta["breakout_level"] == 99.0
    weak = VolumeBreakout().evaluate(ctx(snap(structure=st, rel_volume=0.8)))
    assert weak.signal is None and any("volume" in r for r in weak.reasons)
    assert VolumeBreakout().invalidation(snap(close=97.0), {"breakout_level": 99.0, "bars_held": 2})
    assert VolumeBreakout().invalidation(snap(close=100.0), {"breakout_level": 99.0, "bars_held": 2}) is None


def test_trend_pullback_invalidation():
    assert TrendPullback().invalidation(snap(close=95.0, ema50=97.0, trend="laterale"), {})
    assert TrendPullback().invalidation(snap(), {}) is None


def test_registry():
    assert set(STRATEGIES) == {"trend_following", "trend_pullback", "breakout", "mean_reversion", "volatility_squeeze"}
    assert [s.name for s in build_strategies(["breakout"])] == ["breakout"]
    with pytest.raises(ValueError):
        build_strategies(["inesistente"])
    for d in describe():
        assert d["version"] and d["status"] != "attiva"   # nessuna strategia promossa senza validazione reale
    s = build_strategies(["trend_pullback"], {"trend_pullback": {"target_r": 3.0}})[0]
    assert s.params["target_r"] == 3.0 and s.id == "trend_pullback@1.0.0"


def _signal(entry=100.0, stop=96.0, target=110.0):
    return Signal("BTC/EUR", "t", "1", 0, entry, stop, target, 2.0)


def test_score_bounds_weights_and_categories():
    eng = ScoreEngine(CostModel())
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)
    r = eng.score(_signal(), ctx())
    assert 0 <= r.score <= 100 and set(r.components) == set(DEFAULT_WEIGHTS)
    assert classify(80) == "Opportunità di elevata qualità secondo il modello"
    assert classify(10) == "Nessuna opportunità"
    with pytest.raises(ValueError):
        ScoreEngine(CostModel(), weights={"trend": 0.5})


def test_score_rewards_better_conditions():
    eng = ScoreEngine(CostModel())
    good = eng.score(_signal(), ctx(market=snap(timeframe="4h")))
    bad = eng.score(_signal(), ctx(snap(trend="laterale", adx=12, rsi=74, momentum="negativo in accelerazione", rel_volume=0.4), higher=snap(timeframe="4h", trend="ribassista"), market=snap(trend="ribassista")))
    assert good.score > bad.score + 25


def test_score_penalises_anomaly_and_poor_rr():
    eng = ScoreEngine(CostModel())
    assert eng.score(_signal(), ctx(snap(anomaly=True, anomaly_reason="x"))).components["volatility"] == 0
    assert eng.score(_signal(target=103), ctx()).components["reward_risk"] < 40


def test_volatility_below_costs_scores_low():
    eng = ScoreEngine(CostModel(0.4, 0.05, 0.1))
    assert eng.score(_signal(), ctx(snap(atr_pct=0.5))).components["volatility"] == 10
