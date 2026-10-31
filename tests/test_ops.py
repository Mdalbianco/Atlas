import multiprocessing as mp
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from atlas.ops import AlreadyRunning, SingleInstanceLock, backup_databases, verify_backup
from atlas.storage.db import Database
from tests.test_performance import add_trade


def _try_lock(path, q):
    try:
        SingleInstanceLock(path).acquire()
        q.put("acquisito")
    except AlreadyRunning:
        q.put("bloccato")


def test_second_instance_is_refused(tmp_path):
    with SingleInstanceLock(tmp_path):
        q = mp.Queue()
        p = mp.Process(target=_try_lock, args=(tmp_path, q))
        p.start()
        p.join(10)
        assert q.get(timeout=5) == "bloccato"
    # dopo il rilascio un nuovo processo può partire
    q = mp.Queue()
    p = mp.Process(target=_try_lock, args=(tmp_path, q))
    p.start()
    p.join(10)
    assert q.get(timeout=5) == "acquisito"


def test_backup_rotation_and_integrity(tmp_path):
    db = Database(tmp_path / "atlas.db")
    db.set_state("cash", 42.0)
    Database(tmp_path / "shadow" / "breakout.db").set_state("cash", 1.0)
    start = datetime(2026, 1, 1, 21, tzinfo=timezone.utc)
    for d in range(5):
        files = backup_databases(tmp_path, keep=3, now=start + timedelta(days=d))
    assert {f.name for f in files} == {"atlas-2026-01-05.db", "shadow-breakout-2026-01-05.db"}
    assert len(list((tmp_path / "backups").glob("atlas-*.db"))) == 3
    assert verify_backup(files[0])
    assert Database(files[0]).get_state("cash") == 42.0


def test_daily_and_weekly_reports_sent_once(settings, monkeypatch):
    from atlas.app import Atlas
    from atlas.data.sources import SyntheticMarket
    from atlas.runner import Scheduler
    from atlas.telegram.notifier import NullNotifier
    import atlas.runner as runner

    m = SyntheticMarket({"BTC/EUR": 60000.0}, bars=1000, seed=1)
    n = NullNotifier()
    s = replace(settings, watchlist=("BTC/EUR",), daily_report_hour_utc=0, weekly_report_weekday=datetime.now(timezone.utc).weekday())
    a = Atlas(s, source=m, notifier=n)
    sch = Scheduler(a, 60)
    sch._maybe_daily_report()
    sch._maybe_daily_report()
    assert sum("Riepilogo giornaliero" in t for t in n.sent) == 1
    assert sum("Report settimanale" in t for t in n.sent) == 1
    assert list((s.data_dir / "backups").glob("atlas-*.db"))


def test_proposals_flag_new_only_once(tmp_path):
    from atlas.performance.analyzer import generate_proposals

    db = Database(tmp_path / "p.db")
    for i in range(12):
        add_trade(db, i, -0.5)
    first = generate_proposals(db)
    assert any(p["new"] for p in first)
    assert not any(p["new"] for p in generate_proposals(db))


def test_degradation_detected(tmp_path):
    from atlas.performance.analyzer import degradation_alerts

    db = Database(tmp_path / "d.db")
    for i in range(16):
        add_trade(db, i, -0.6)
    alerts = degradation_alerts(db)
    assert alerts and alerts[0]["kind"] == "degrado" and "trend_pullback" in alerts[0]["title"]


def test_export_restore_roundtrip(tmp_path):
    import tarfile

    from atlas.ops import export_state, restore_state

    src, dst = tmp_path / "codespace", tmp_path / "server"
    db = Database(src / "atlas.db")
    db.set_state("cash", 77.0)
    add_trade(db, 1, 0.5)
    Database(src / "shadow" / "breakout.db").set_state("cash", 91.0)
    (src / ".env").write_text("TELEGRAM_TOKEN=segreto")
    m = export_state(src, tmp_path / "x.tar.gz")
    assert m["databases"]["atlas.db"]["positions"] == 1
    with tarfile.open(tmp_path / "x.tar.gz") as t:
        assert ".env" not in t.getnames() and all(".env" not in n for n in t.getnames())
    Database(dst / "atlas.db").set_state("cash", 1.0)          # dati già presenti sul server
    restore_state(dst, tmp_path / "x.tar.gz")
    assert Database(dst / "atlas.db").get_state("cash") == 77.0
    assert Database(dst / "shadow" / "breakout.db").get_state("cash") == 91.0
    backups = list(dst.glob("pre-restore-*/atlas.db"))
    assert backups and Database(backups[0]).get_state("cash") == 1.0   # nulla perso


def test_restore_refused_while_running(tmp_path):
    from atlas.ops import export_state, restore_state

    Database(tmp_path / "a" / "atlas.db").set_state("cash", 5.0)
    export_state(tmp_path / "a", tmp_path / "x.tar.gz")
    with SingleInstanceLock(tmp_path / "b"):
        with pytest.raises(AlreadyRunning):
            # il lock è per processo: simuliamo un'istanza attiva in un altro processo
            q = mp.Queue()
            p = mp.Process(target=_restore_in_child, args=(tmp_path / "b", tmp_path / "x.tar.gz", q))
            p.start(); p.join(20)
            raise q.get(timeout=5)


def _restore_in_child(data_dir, archive, q):
    from atlas.ops import restore_state

    try:
        restore_state(data_dir, archive)
        q.put(RuntimeError("ripristino eseguito con ATLAS attivo"))
    except AlreadyRunning as exc:
        q.put(exc)


def test_restore_rejects_malicious_archive(tmp_path):
    import io
    import json
    import tarfile

    from atlas.ops import restore_state

    bad = tmp_path / "bad.tar.gz"
    with tarfile.open(bad, "w:gz") as t:
        for name, data in (("manifest.json", json.dumps({"databases": {}}).encode()), ("../evil.db", b"x")):
            info = tarfile.TarInfo(name); info.size = len(data); t.addfile(info, io.BytesIO(data))
    with pytest.raises(ValueError):
        restore_state(tmp_path / "srv", bad)


def test_doctor_offline_and_with_market(settings):
    from atlas.data.sources import SyntheticMarket
    from atlas.doctor import render, run_checks

    m = SyntheticMarket({"BTC/EUR": 60000.0}, bars=800, seed=2)
    last = int(m.data["BTC/EUR"].timestamp.iloc[-1])
    s = replace(settings, watchlist=("BTC/EUR",), telegram_token="123456:" + "S" * 35, telegram_chat_id="1", telegram_allowed_users=frozenset({1}))
    checks = run_checks(s, network=False)
    text, code = render(checks)
    assert "PAPER TRADING" in text and "bloccati" in text
    assert "S" * 35 not in text                         # il token non compare mai
    assert code == 0
    import atlas.data.market_data as md
    checks = run_checks(s, network=True, source=m)
    assert any(c.name == "Kraken BTC/EUR" and c.ok for c in checks) or any(c.name == "Kraken" for c in checks)
