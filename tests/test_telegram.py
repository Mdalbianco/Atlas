from dataclasses import replace

import pytest

from atlas.app import Atlas
from atlas.data.sources import SyntheticMarket
from atlas.telegram.bot import AccessControl, CommandRouter
from atlas.telegram.notifier import NullNotifier
from tests.conftest import Clock

USER, ADMIN, STRANGER = 111, 222, 999


@pytest.fixture
def router(settings):
    m = SyntheticMarket({"BTC/EUR": 60000.0, "ETH/EUR": 3000.0}, bars=1100, seed=5)
    last = int(m.data["BTC/EUR"].timestamp.iloc[-1])
    s = replace(settings, watchlist=("BTC/EUR", "ETH/EUR"))
    atlas = Atlas(s, source=m, notifier=NullNotifier(), clock=Clock(last + 3_600_000 + 60_000))
    return CommandRouter(atlas, AccessControl(frozenset({USER}), frozenset({ADMIN})))


def test_fail_closed_without_configured_users(settings):
    ac = AccessControl(frozenset(), frozenset())
    assert not ac.can_use(123) and not ac.can_use(None)


def test_unauthorized_user_is_rejected(router):
    assert "non autorizzato" in router.handle("/status", [], STRANGER)
    assert "non autorizzato" in router.handle("/status", [], None)


def test_admin_commands_protected(router):
    for cmd in ("/pausa", "/riprendi", "/config", "/chiudi", "/modalita"):
        assert "amministratori" in router.handle(cmd, [], USER)
    assert "sospese" in router.handle("/pausa", [], ADMIN)
    assert "ripresa" in router.handle("/riprendi", [], ADMIN)


@pytest.mark.parametrize(
    "cmd,args,expected",
    [
        ("/start", [], "PAPER TRADING"),
        ("/help", [], "/analisi"),
        ("/status", [], "Stato"),
        ("/saldo", [], "Saldo simulato"),
        ("/prezzo", ["BTC"], "BTC/EUR"),
        ("/watchlist", [], "ETH/EUR"),
        ("/analisi", ["BTC"], "Analisi BTC/EUR"),
        ("/segnali", [], "decision"),
        ("/mercato", [], "Panoramica"),
        ("/strategie", [], "trend_pullback"),
        ("/posizioni", [], "posizion"),
        ("/operazioni", [], "operazion"),
        ("/performance", [], "statistiche"),
        ("/report", [], "Proposte"),
        ("/rischio", [], "Rischio per operazione"),
        ("/analizza", ["ETH"], "ETH/EUR"),
    ],
)
def test_user_commands(router, cmd, args, expected):
    out = router.handle(cmd, args, USER)
    assert expected.lower() in out.lower(), out


def test_admin_info_commands(router):
    cfg = router.handle("/config", [], ADMIN)
    assert "non configurato" in cfg and "telegram_token" in cfg
    assert "docs/LIVE_TRADING_POLICY.md" in router.handle("/modalita", [], ADMIN)


def test_watchlist_management(router):
    assert "Solo gli amministratori" in router.handle("/watchlist", ["add", "SOL"], USER)
    assert "non risulta disponibile" in router.handle("/watchlist", ["add", "XYZ"], ADMIN)
    assert "rimossa" in router.handle("/watchlist", ["remove", "ETH"], ADMIN)
    assert "ETH/EUR" not in router.handle("/watchlist", [], USER)


def test_analysis_explains_and_does_not_trade(router):
    out = router.handle("/analisi", ["BTC"], USER)
    assert "Decisione" in out and "NON la probabilità" in out
    assert router.atlas.db.open_positions() == []


def test_unknown_and_missing_args(router):
    assert "non riconosciuto" in router.handle("/boh", [], USER)
    assert "Uso" in router.handle("/prezzo", [], USER)


def test_errors_are_reported_not_raised(router):
    out = router.handle("/prezzo", ["NONESISTE"], USER)
    assert out.startswith("❌")


def test_resume_after_halt_requires_confirmation(router):
    router.atlas.cycle.account.halt("drawdown 16% oltre il limite")
    assert "conferma" in router.handle("/riprendi", [], ADMIN)
    assert router.atlas.db.get_state("halted") is True
    assert "ripresa" in router.handle("/riprendi", ["conferma"], ADMIN)
    assert router.atlas.db.get_state("halted") is False


def test_python_telegram_bot_integration(router, monkeypatch):
    """Costruisce l'Application reale e simula un update /status, intercettando la risposta."""
    import asyncio

    pytest.importorskip("telegram")
    from telegram import Chat, Message, Update, User
    from telegram.ext import CommandHandler

    from atlas.telegram.bot import build_application

    atlas = router.atlas
    atlas.settings = replace(atlas.settings, telegram_token="123456:" + "A" * 35, telegram_allowed_users=frozenset({USER}))
    app = build_application(atlas)
    handler = next(h for group in app.handlers.values() for h in group if isinstance(h, CommandHandler))
    assert {"status", "analisi", "pausa", "rischio", "watchlist"} <= set(handler.commands)

    replies = []

    async def fake_reply(self, text, **kw):
        replies.append(text)

    monkeypatch.setattr(Message, "reply_text", fake_reply)

    async def run():
        from datetime import datetime, timezone

        msg = Message(1, datetime.now(timezone.utc), Chat(1, "private"), from_user=User(USER, "u", False), text="/status")
        msg._unfreeze()
        from telegram import MessageEntity

        msg.entities = (MessageEntity("bot_command", 0, 7),)
        msg.set_bot(app.bot)
        upd = Update(1, message=msg)
        await handler.callback(upd, None)

    asyncio.run(run())
    assert replies and "Stato" in replies[0]


def test_strategies_and_comparison_texts(router):
    out = router.handle("/strategie", [], USER)
    for name in ("trend_pullback", "breakout"):
        assert name in out
    assert "PRINCIPALE" in router.atlas.text_comparison()


def test_conflict_monitor_rate_limited(router):
    from atlas.telegram.bot import ConflictMonitor

    t = {"now": 1000.0}
    mon = ConflictMonitor(router.atlas, every_seconds=3600, clock=lambda: t["now"])
    sent_before = len(router.atlas.notifier.sent)
    assert mon.report() is True
    assert mon.report() is False            # stessa ora: nessun nuovo messaggio
    t["now"] += 3601
    assert mon.report() is True
    assert len(router.atlas.notifier.sent) - sent_before == 2
    assert any(e["type"] == "telegram_conflict" for e in router.atlas.db.query("SELECT type FROM events"))


def test_diagnostics_command(router):
    out = router.handle("/diagnosi", [], USER)
    assert "Diagnosi delle strategie" in out
