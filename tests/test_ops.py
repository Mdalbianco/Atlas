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
