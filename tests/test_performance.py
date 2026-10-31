import json
from datetime import datetime, timedelta, timezone

from atlas.performance.analyzer import generate_proposals, performance_summary
from atlas.storage.db import Database


def add_trade(db, i, pnl, strategy="trend_pullback", score=70.0, reason="stop_loss", fees=0.2):
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=10 * i)
    db.execute(
        """INSERT INTO positions(symbol, strategy, strategy_version, status, opened_at, closed_at, signal_bar_ts, entry_price, quantity,
           entry_fee, initial_stop, stop_loss, take_profit, risk_amount, highest_price, score, market_context, exit_price, exit_fee,
           exit_reason, pnl, pnl_pct, r_multiple, client_order_id)
           VALUES ('BTC/EUR', ?, '1', 'closed', ?, ?, ?, 100, 0.2, ?, 97, 97, 106, 1, 100, ?, ?, 100, ?, ?, ?, ?, ?, ?)""",
        (strategy, t0.isoformat(), (t0 + timedelta(hours=5)).isoformat(), i, fees / 2, score, json.dumps({"primary": {"regime": "laterale"}}), fees / 2, reason, pnl, pnl, pnl, f"id{i}"),
    )


def test_summary_and_proposals(tmp_path):
    db = Database(tmp_path / "p.db")
    assert generate_proposals(db)[0]["kind"] == "dati_insufficienti"
    for i in range(12):
        add_trade(db, i, -0.5 if i % 3 else 0.6, score=58.0 if i < 6 else 80.0)
    s = performance_summary(db)
    assert s["overall"]["trades"] == 12 and s["fees_total"] > 0
    props = generate_proposals(db)
    kinds = {p["kind"] for p in props}
    assert "escludere_strategy" in kinds
    assert all("preliminare" in p["title"] for p in props)
    saved = db.query("SELECT * FROM proposals")
    assert saved and all(r["status"] == "proposta" for r in saved)
    generate_proposals(db)
    assert len(db.query("SELECT * FROM proposals")) == len(saved)   # niente duplicati


def test_fee_drag_detected(tmp_path):
    db = Database(tmp_path / "f.db")
    for i in range(10):
        add_trade(db, i, -0.05, fees=0.3)   # lordo +0.25, netto -0.05
    assert "costi" in {p["kind"] for p in generate_proposals(db, save=False)}
