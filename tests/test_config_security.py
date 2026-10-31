import logging

import pytest

from atlas.config import ConfigError, Settings, load_settings, normalize_symbol
from atlas.data.exchange import ReadOnlyExchange, with_retries, ExchangeUnavailable
from atlas.execution.live import LiveBroker, LiveTradingDisabled
from atlas.logging_setup import RedactingFilter, redact, register_secret


def test_default_mode_is_paper(monkeypatch):
    monkeypatch.delenv("ATLAS_MODE", raising=False)
    s = load_settings(env_file=None)
    assert s.mode == "paper"
    assert s.initial_capital == 100.0


def test_live_mode_is_rejected(monkeypatch):
    monkeypatch.setenv("ATLAS_MODE", "live")
    with pytest.raises(ConfigError, match="paper"):
        load_settings(env_file=None)


def test_live_broker_cannot_be_instantiated():
    with pytest.raises(LiveTradingDisabled):
        LiveBroker()


def test_invalid_risk_rejected(monkeypatch):
    monkeypatch.setenv("ATLAS_RISK_PER_TRADE_PCT", "5")
    with pytest.raises(ConfigError):
        load_settings(env_file=None)


def test_env_parsing(monkeypatch):
    monkeypatch.setenv("ATLAS_WATCHLIST", "btc, eth/eur")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "123,456")
    monkeypatch.setenv("ATLAS_MIN_SCORE", "70,5")
    s = load_settings(env_file=None)
    assert s.watchlist == ("BTC/EUR", "ETH/EUR")
    assert s.telegram_allowed_users == frozenset({123, 456})
    assert s.min_score == 70.5
    assert normalize_symbol("sol") == "SOL/EUR"


def test_redacted_config_hides_secrets():
    s = Settings(telegram_token="123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi", kraken_api_key="KEY123456", kraken_api_secret="SECRET123456")
    red = s.redacted()
    text = str(red)
    assert "KEY123456" not in text and "SECRET123456" not in text and "ABCDEFGHIJ" not in text
    assert red["telegram_token"] == "***configurato***"
    assert "SECRET123456" not in repr(s)


def test_log_redaction():
    token = "987654321:AAHfakeTokenValue_abcdefghijklmnopqrs"
    assert token not in redact(f"url https://api.telegram.org/bot{token}/sendMessage")
    assert "supersecretvalue" not in redact('{"secret": "supersecretvalue"}')
    register_secret("my-registered-secret")
    assert "my-registered-secret" not in redact("x my-registered-secret y")
    rec = logging.LogRecord("t", logging.INFO, "", 0, "api_key=%s", ("abcdef123",), None)
    RedactingFilter().filter(rec)
    assert "abcdef123" not in rec.getMessage()


class FakeCcxt:
    def fetch_ticker(self, s):
        return {"last": 1}

    def create_order(self, *a):  # pragma: no cover - non deve mai essere chiamato
        raise AssertionError("ordine inviato!")

    def withdraw(self, *a):  # pragma: no cover
        raise AssertionError("prelievo!")


def test_read_only_exchange_blocks_trading_methods():
    ex = ReadOnlyExchange(FakeCcxt())
    assert ex.fetch_ticker("BTC/EUR") == {"last": 1}
    for name in ("create_order", "withdraw", "cancel_order", "create_market_buy_order", "private_post_addorder"):
        with pytest.raises(PermissionError):
            getattr(ex, name)


def test_no_order_methods_in_codebase():
    """Nessun file del package deve invocare endpoint di trading reale."""
    from pathlib import Path

    import atlas

    forbidden = ("create_order(", "create_market", "create_limit", "withdraw(", "cancel_order(", "privatePostAddOrder", "private_post_add_order")
    root = Path(atlas.__file__).parent
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for f in forbidden:
            assert f not in text, f"{f} trovato in {path}"


def test_retries_with_backoff():
    calls, sleeps = [], []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise TimeoutError()
        return "ok"

    assert with_retries(flaky, retries=4, retry_on=(TimeoutError,), sleep=sleeps.append) == "ok"
    assert sleeps == [1.0, 2.0]
    with pytest.raises(ExchangeUnavailable):
        with_retries(lambda: (_ for _ in ()).throw(TimeoutError()), retries=2, retry_on=(TimeoutError,), sleep=lambda s: None)


def test_real_kraken_client_is_read_only_even_with_keys():
    pytest.importorskip("ccxt")
    from atlas.data.exchange import KrakenDataSource

    src = KrakenDataSource(api_key="finta-chiave-123456", api_secret="ZmludG8tc2VncmV0by0xMjM0NTY=")
    assert isinstance(src._exchange, ReadOnlyExchange)
    for name in ("create_order", "create_market_buy_order", "cancel_order", "withdraw", "transfer", "private_post_add_order", "edit_order"):
        with pytest.raises(PermissionError):
            getattr(src._exchange, name)


def test_no_execution_path_to_live_broker():
    """Nessun modulo operativo importa o istanzia LiveBroker."""
    from pathlib import Path

    import atlas

    root = Path(atlas.__file__).parent
    users = [p for p in root.rglob("*.py") if "LiveBroker" in p.read_text(encoding="utf-8") and p.name != "live.py"]
    # unica eccezione ammessa: doctor.py, che istanzia LiveBroker SOLO per verificare che si rifiuti
    assert [p.name for p in users] in ([], ["doctor.py"])
    if users:
        text = users[0].read_text(encoding="utf-8")
        assert "except LiveTradingDisabled" in text and text.count("LiveBroker()") == 1
