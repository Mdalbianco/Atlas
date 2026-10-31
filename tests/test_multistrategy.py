import json
from dataclasses import replace

import pytest

from atlas.config import ConfigError, Settings, load_settings
from atlas.domain import Action, MarketRules
from atlas.engine.decision import DecisionEngine
from atlas.risk.costs import CostModel, net_reward_risk
from atlas.risk.manager import PortfolioState, RiskLimits, RiskManager
from atlas.scoring import ScoreEngine
from atlas.strategy.mean_reversion import MeanReversion
from atlas.strategy.registry import STRATEGIES, build_strategies
from atlas.strategy.trend_following import TrendFollowing
from atlas.strategy.validation import CRITERIA, evaluate_criteria, split_active_shadow, status_of
from atlas.strategy.volatility_squeeze import VolatilitySqueeze
from tests.factories import ctx, snap, structure

from datetime import datetime, timezone

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


# --- trend following -------------------------------------------------------
def test_trend_following_entry_and_invalidation():
    p = snap(ema_cross_up=True, adx=25.0, adx_slope=1.0)
    ev = TrendFollowing().evaluate(ctx(p))
    assert ev.signal is not None
    s = ev.signal
    assert s.entry_price - s.stop_loss == pytest.approx(2.5 * p.atr)
    assert net_reward_risk(s.entry_price, s.stop_loss, s.take_profit, CostModel().with_spread(0.05))[0] == pytest.approx(4.0, rel=1e-6)
    assert TrendFollowing().invalidation(snap(ema20=96.0, ema50=97.0), {})
    assert TrendFollowing().invalidation(snap(), {}) is None


@pytest.mark.parametrize("override", [{"ema_cross_up": False}, {"adx_slope": -0.5}, {"ema50": 89.0}, {"rsi": 80.0}])
def test_trend_following_rejections(override):
    base = dict(ema_cross_up=True, adx=25.0, adx_slope=1.0)
    base.update(override)
    assert TrendFollowing().evaluate(ctx(snap(**base))).signal is None


def test_trend_following_needs_bullish_higher_tf():
    p = snap(ema_cross_up=True, adx=25.0, adx_slope=1.0)
    assert TrendFollowing().evaluate(ctx(p, higher=snap(timeframe="4h", trend="laterale"))).signal is None


# --- mean reversion --------------------------------------------------------
def _mr_snap(**kw):
    base = dict(regime="laterale", trend="laterale", adx=14.0, close=95.5, open=94.8, low=94.0, bb_lower=94.5, bb_mid=99.0, bb_upper=103.5, rsi=30.0, atr=1.5)
    base.update(kw)
    return snap(**base)


def test_mean_reversion_only_in_range_regime():
    ev = MeanReversion().evaluate(ctx(_mr_snap(), higher=snap(timeframe="4h", trend="laterale")))
    assert ev.signal is not None and ev.signal.take_profit == 99.0
    assert MeanReversion().evaluate(ctx(_mr_snap(regime="trend_ribassista", adx=30))).signal is None
    assert MeanReversion().evaluate(ctx(_mr_snap(), higher=snap(timeframe="4h", trend="ribassista"))).signal is None
    assert MeanReversion().evaluate(ctx(_mr_snap(close=94.5, open=95.0))).signal is None  # nessuna candela di inversione
    assert MeanReversion().invalidation(_mr_snap(regime="trend_ribassista"), {})


# --- volatility squeeze -----------------------------------------------------
def test_volatility_squeeze():
    p = snap(bb_width_rank_prev=0.1, bb_upper=99.5, bb_mid=97.0, rel_volume=1.6, rsi=64.0)
    ev = VolatilitySqueeze().evaluate(ctx(p))
    assert ev.signal is not None and ev.signal.stop_loss <= 97.0
    assert VolatilitySqueeze().evaluate(ctx(snap(bb_width_rank_prev=0.6, bb_upper=99.5, rel_volume=1.6))).signal is None
    assert VolatilitySqueeze().invalidation(snap(close=96.0, bb_mid=97.0), {"bars_held": 2})


# --- regime gating ---------------------------------------------------------
def test_no_strategy_trades_in_downtrend_or_extreme_volatility():
    eng = DecisionEngine(build_strategies(list(STRATEGIES)), ScoreEngine(CostModel()), RiskManager(RiskLimits(), CostModel()), 0)
    state = PortfolioState(100, 100, 100, 100)
    rules = MarketRules("BTC/EUR", min_cost=0.5)
    for regime in ("trend_ribassista", "alta_volatilita"):
        d = eng.decide_entry(ctx(snap(regime=regime, ema_cross_up=True, adx_slope=1.0)), state, rules, NOW)
        assert d.action is Action.SKIP
        assert all("non compatibile" in r for r in d.reasons)


def test_every_strategy_has_versions_regimes_and_params():
    for cls in STRATEGIES.values():
        s = cls()
        assert s.version and s.regimes and isinstance(s.default_params(), dict) and s.description
        assert "trend_ribassista" not in s.regimes and "alta_volatilita" not in s.regimes


# --- cancello di validazione ---------------------------------------------------
def test_validation_gate(tmp_path):
    path = tmp_path / "v.json"
    strategies = build_strategies(["trend_pullback", "breakout"])
    active, shadow = split_active_shadow(strategies, True, path)
    assert active == [] and len(shadow) == 2   # nessun file → nessuna strategia attiva
    path.write_text(json.dumps({"strategies": {"breakout@1.0.0": {"status": "validata"}, "trend_pullback@0.9.0": {"status": "validata"}}}))
    active, shadow = split_active_shadow(strategies, True, path)
    assert [s.name for s in active] == ["breakout"]          # la versione deve coincidere esattamente
    assert status_of(strategies[0], path).status == "non_validata"
    assert split_active_shadow(strategies, False, path) == (strategies, [])


def test_validation_criteria():
    good = {"trades": 80, "expectancy_r": 0.2, "profit_factor": 1.5}
    ok, fails = evaluate_criteria(good, max_dd=8.0, positive_folds_ratio=0.75)
    assert ok and not fails
    ok, fails = evaluate_criteria({"trades": 10, "expectancy_r": -0.1, "profit_factor": 0.8}, max_dd=20.0, positive_folds_ratio=0.2)
    assert not ok and len(fails) == 5


def test_repository_status_file_promotes_nothing_without_evidence():
    from atlas.strategy.validation import load_status

    for key, entry in load_status().items():
        if entry.get("status") == "validata":
            ok, _ = evaluate_criteria(entry["oos"], entry["max_drawdown_pct"], entry["positive_folds_ratio"])
            assert ok, f"{key} risulta validata senza soddisfare i criteri"


# --- book ombra --------------------------------------------------------------
def test_shadow_books_are_isolated(settings):
    from atlas.app import Atlas
    from atlas.data.sources import SyntheticMarket
    from atlas.telegram.notifier import NullNotifier
    from tests.conftest import Clock

    m = SyntheticMarket({"BTC/EUR": 60000.0}, bars=1300, seed=3)
    t = int(m.data["BTC/EUR"].timestamp.iloc[1100])
    m.now_ms = t
    s = replace(settings, watchlist=("BTC/EUR",), market_reference="BTC/EUR", require_validation=True, shadow_strategies=True, strategies=("trend_pullback", "mean_reversion"))
    notifier = NullNotifier()
    a = Atlas(s, source=m, notifier=notifier, clock=Clock(t + 60_000))
    assert a.cycle.strategies == {}                      # nessuna strategia validata → principale fermo
    assert sorted(b.name for b in a.cycle.shadow_books) == ["mean_reversion", "trend_pullback"]
    rep = a.cycle.run_once()
    assert rep.ok
    assert a.db.query("SELECT COUNT(*) c FROM decisions")[0]["c"] == 0       # il principale non valuta nulla
    for b in a.cycle.shadow_books:
        assert b.db.path != a.db.path
        assert b.db.query("SELECT COUNT(*) c FROM decisions")[0]["c"] == 1   # ogni ombra valuta per conto suo
    assert not any("aperta" in n for n in notifier.sent)


# --- configurazione sicura -----------------------------------------------------
def test_unknown_atlas_variable_stops_startup(monkeypatch):
    monkeypatch.setenv("ATLAS_MAX_DRAWDWON_PCT", "50")   # errore di battitura
    with pytest.raises(ConfigError, match="non riconosciute"):
        load_settings(env_file=None)


def test_ambiguous_telegram_or_kraken_config_rejected():
    with pytest.raises(ConfigError, match="ambigua"):
        Settings(telegram_token="1:x", telegram_chat_id="1").validate()
    with pytest.raises(ConfigError, match="insieme"):
        Settings(kraken_api_key="k").validate()
    with pytest.raises(ConfigError, match="sconosciuta"):
        Settings(strategies=("magia",)).validate()


def test_validation_runner_end_to_end_on_synthetic(tmp_path):
    from atlas.backtest.engine import BacktestConfig
    from atlas.backtest.validation_runner import markdown, validate_all, write_status
    from atlas.data.sources import SyntheticMarket
    from atlas.strategy.validation import load_status

    data = SyntheticMarket(bars=2400, seed=11).data
    rep = validate_all(data, BacktestConfig(), ["trend_pullback"], train_bars=800, test_bars=400, warmup_bars=900, source="sintetici di test")
    r = rep["results"][0]
    assert r["folds"] and all(f["train"][1] <= f["test"][0] for f in r["folds"])
    assert r["configurations_tested"] == 3 * 2
    assert r["status"] in ("validata", "respinta")
    assert "sintetici di test" in markdown(rep)
    path = tmp_path / "status.json"
    write_status(rep, path)
    entry = load_status(path)["trend_pullback@1.0.0"]
    assert entry["status"] == r["status"] and "oos" in entry
    with pytest.raises(ValueError):
        validate_all(data, BacktestConfig(), ["trend_pullback"], grids={"trend_pullback": {"inesistente": [1.0]}})
