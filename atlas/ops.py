"""Operatività: istanza unica, backup del database, informazioni di salute."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from atlas.logging_setup import get_logger

log = get_logger(__name__)


class AlreadyRunning(RuntimeError):
    pass


class SingleInstanceLock:
    """Impedisce due processi ATLAS sulla stessa cartella dati.

    Due istanze contemporanee entrerebbero in conflitto sul polling Telegram
    (errore 409) e valuterebbero due volte le stesse candele. Il lock usa
    ``fcntl.flock``: viene rilasciato automaticamente dal sistema operativo
    anche se il processo termina in modo anomalo (nessun lock "orfano").
    """

    def __init__(self, data_dir: str | Path) -> None:
        self.path = Path(data_dir) / "atlas.lock"
        self._fh = None

    def acquire(self) -> "SingleInstanceLock":
        import fcntl

        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+", encoding="utf-8")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            fh.seek(0)
            owner = fh.read().strip() or "sconosciuto"
            fh.close()
            raise AlreadyRunning(f"un'altra istanza di ATLAS è già in esecuzione su {self.path.parent} ({owner})") from exc
        fh.seek(0)
        fh.truncate()
        fh.write(f"pid={os.getpid()} avvio={datetime.now(timezone.utc).isoformat()}")
        fh.flush()
        self._fh = fh
        return self

    def release(self) -> None:
        if self._fh is not None:
            import fcntl

            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "SingleInstanceLock":
        return self.acquire()

    def __exit__(self, *exc) -> None:
        self.release()


def backup_databases(data_dir: str | Path, keep: int = 14, now: datetime | None = None) -> list[Path]:
    """Copia coerente (API di backup SQLite, sicura anche con il processo attivo) di tutti i database.

    Un file al giorno per database in ``data/backups/``; si conservano gli ultimi ``keep`` giorni.
    """
    data_dir = Path(data_dir)
    now = now or datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")
    dest_dir = data_dir / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    sources = [data_dir / "atlas.db", *sorted((data_dir / "shadow").glob("*.db"))]
    written = []
    for src in sources:
        if not src.exists():
            continue
        label = src.stem if src.parent == data_dir else f"shadow-{src.stem}"
        dest = dest_dir / f"{label}-{day}.db"
        with sqlite3.connect(src) as s_conn, sqlite3.connect(dest) as d_conn:
            s_conn.backup(d_conn)
        written.append(dest)
        # rotazione
        copies = sorted(dest_dir.glob(f"{label}-*.db"))
        for old in copies[:-keep]:
            old.unlink()
    log.info("backup completato", extra={"data": {"files": [p.name for p in written]}})
    return written


def verify_backup(path: str | Path) -> bool:
    """Verifica di integrità SQLite di un backup."""
    with sqlite3.connect(path) as conn:
        return conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
