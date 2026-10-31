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


def _db_files(data_dir: Path) -> list[Path]:
    return [p for p in [data_dir / "atlas.db", *sorted((data_dir / "shadow").glob("*.db"))] if p.exists()]


def export_state(data_dir: str | Path, out: str | Path) -> dict:
    """Archivio .tar.gz di tutti i portafogli (principale + ombra) per il trasferimento su un altro server.

    Usa l'API di backup SQLite (copia coerente anche con ATLAS in esecuzione).
    NON include mai .env né altri file di configurazione: i segreti restano dove sono.
    """
    import json
    import tarfile
    import tempfile

    from atlas import __version__

    data_dir, out = Path(data_dir), Path(out)
    files = _db_files(data_dir)
    if not files:
        raise FileNotFoundError(f"nessun database ATLAS in {data_dir}")
    manifest = {"atlas_version": __version__, "exported_at": datetime.now(timezone.utc).isoformat(), "databases": {}}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        with tarfile.open(out, "w:gz") as tar:
            for src in files:
                rel = src.relative_to(data_dir)
                dest = tmp / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                with sqlite3.connect(src) as s_conn, sqlite3.connect(dest) as d_conn:
                    s_conn.backup(d_conn)
                with sqlite3.connect(dest) as c:
                    manifest["databases"][str(rel)] = {
                        "positions": c.execute("SELECT COUNT(*) FROM positions").fetchone()[0],
                        "decisions": c.execute("SELECT COUNT(*) FROM decisions").fetchone()[0],
                    }
                tar.add(dest, arcname=str(rel))
            mpath = tmp / "manifest.json"
            mpath.write_text(json.dumps(manifest, indent=2))
            tar.add(mpath, arcname="manifest.json")
    return manifest


def restore_state(data_dir: str | Path, archive: str | Path) -> dict:
    """Ripristina un archivio creato da :func:`export_state`.

    Rifiuta se ATLAS è in esecuzione sulla stessa cartella; i database esistenti vengono
    spostati in ``data/pre-restore-<data>/`` (nulla viene cancellato).
    """
    import json
    import tarfile

    data_dir, archive = Path(data_dir), Path(archive)
    with SingleInstanceLock(data_dir):
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            names = {m.name for m in members}
            if "manifest.json" not in names:
                raise ValueError("archivio non valido: manifest.json mancante")
            for m in members:
                ok_name = m.name == "manifest.json" or (m.name.endswith(".db") and (m.name == "atlas.db" or m.name.startswith("shadow/")))
                if not m.isfile() or not ok_name or ".." in Path(m.name).parts or m.name.startswith("/"):
                    raise ValueError(f"contenuto non ammesso nell'archivio: {m.name}")
            manifest = json.load(tar.extractfile("manifest.json"))
            existing = _db_files(data_dir)
            if existing:
                keep = data_dir / f"pre-restore-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
                for f in existing:
                    target = keep / f.relative_to(data_dir)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    f.rename(target)
                    for suffix in ("-wal", "-shm"):
                        side = f.with_name(f.name + suffix)
                        if side.exists():
                            side.rename(target.with_name(target.name + suffix))
            for m in members:
                if m.name.endswith(".db"):
                    dest = data_dir / m.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with tar.extractfile(m) as src, open(dest, "wb") as fh:
                        fh.write(src.read())
                    if not verify_backup(dest):
                        raise ValueError(f"database corrotto nell'archivio: {m.name}")
    return manifest
