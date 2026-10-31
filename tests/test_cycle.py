from dataclasses import replace

import pytest

from atlas.app import Atlas
from atlas.data.sources import SyntheticMarket
from atlas.strategy.base import Evaluation, Strategy
from atlas.telegram.notifier import NullNotifier
from tests.conftest import Clock

H = 3_600_000


class AlwaysLong(Strategy):
    """Strategia di test: segnala sempre (serve a esercitare il percorso di esecuzione)."""

    name = "always_long"
    version = "test"

    def evaluate(self, ctx):
        p = ctx.primary
        return Evaluation(self._make_signal(ctx, p.close - 2 * p.atr, p.close + 6 * p.atr, ["test"], ["test"]), ["test"])

    def invalidation(self, snap, meta):
        return None


@pytest.fixture
def env(settings):
    m = SyntheticMarket({"BTC/EUR": 60000.0, "ETH/EUR": 3000.0}, bars=1300, seed=3)
    ts = m.data["BTC/EUR"].timestamp.tolist()
    clock = Clock(0)
    s = replace(settings, watchlist=("BTC/EUR", "ETH/EUR"), min_score=0.0)
    notifier = NullNotifier()

    def at(i):
        m.now_ms = ts[i]
        clock.ms = ts[i] + 60_000

    def make():
        a = Atlas(s, source=m, notifier=notifier, clock=clock)
        a.cycle.engine.strategies = [AlwaysLong()]
        a.cycle.strategies.clear()
        a.cycle.strategies["always_long"] = AlwaysLong()
        return a

    return {"m": m, "at": at, "make": make, "notifier": notifier, "settings": s}


def test_cycle_opens_manages_and_survives_restart(env):
    a = env["make"]()
    env["at"](1000)
    rep = a.cycle.run_once()
    assert rep.ok, rep.errors
    assert len(rep.opened) >= 1
    assert any("aperta" in t for t in env["notifier"].sent)
    # stesso istante: la candela è già stata valutata → nessun nuovo ordine
    rep2 = a.cycle.run_once()
    assert not rep2.opened
    n_orders = len(a.db.query("SELECT * FROM orders"))
    # riavvio: nuovo processo, stesso database
    a.db.close()
    a = env["make"]()
    rep3 = a.cycle.run_once()
    assert rep3.ok and not rep3.opened
    assert len(a.db.query("SELECT * FROM orders")) == n_orders
    for i in range(1001, 1120):
        env["at"](i)
        assert a.cycle.run_once().ok
    orders = a.db.query("SELECT client_order_id FROM orders")
    assert len(orders) == len({o["client_order_id"] for o in orders})
    assert len(a.db.closed_positions()) >= 1
    st = a.cycle.account.state()
    total_pnl = sum(p["pnl"] for p in a.db.closed_positions())
    open_cost = sum(p["entry_price"] * p["quantity"] + p["entry_fee"] for p in a.db.open_positions())
    assert st.cash == pytest.approx(100.0 + total_pnl - open_cost, abs=1e-6)
    assert a.db.get_state("heartbeat")


def test_exchange_down_is_not_critical(env):
    a = env["make"]()
    env["at"](1000)
    env["m"].ping = lambda: False
    rep = a.cycle.run_once()
    assert not rep.ok
    assert not a.db.get_state("halted")
    assert a.db.get_state("consecutive_errors") == 1


def test_unexpected_error_triggers_safety_halt(env):
    a = env["make"]()
    env["at"](1000)

    def boom(symbol):
        raise RuntimeError("bug imprevisto")

    env["m"].fetch_ticker = boom
    rep = a.cycle.run_once()
    assert not rep.ok
    assert a.db.get_state("halted") is True
    assert any("ARRESTO" in t for t in env["notifier"].sent)
    # in arresto non si aprono posizioni anche se il problema sparisce
    del env["m"].fetch_ticker
    env["at"](1001)
    rep = a.cycle.run_once()
    assert rep.ok and not rep.opened


def test_pause_blocks_new_entries(env):
    a = env["make"]()
    a.cycle.account.set_paused(True)
    env["at"](1000)
    rep = a.cycle.run_once()
    assert rep.ok and not rep.opened
    assert any("pausa" in b for b in rep.blocks)
