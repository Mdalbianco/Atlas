"""Persistenza SQLite di ATLAS.

Scelte di robustezza:
- modalità WAL e ``synchronous=NORMAL``: sopravvive ai riavvii senza corruzione;
- ogni scrittura multi-tabella avviene in una transazione;
- ``orders.client_order_id`` è UNIQUE: lo stesso segnale non può generare due
  ordini nemmeno dopo un crash a metà ciclo;
- indice parziale UNIQUE su ``positions(symbol) WHERE status='open'``:
  impossibile avere due posizioni aperte sulla stessa coppia.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'paper',
    strategy TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open','closed')),
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    signal_bar_ts INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    quantity REAL NOT NULL,
    entry_fee REAL NOT NULL,
    initial_stop REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit REAL NOT NULL,
    risk_amount REAL NOT NULL,
    highest_price REAL NOT NULL,
    bars_held INTEGER NOT NULL DEFAULT 0,
    last_bar_ts INTEGER,
    trailing_active INTEGER NOT NULL DEFAULT 0,
    score REAL,
    score_category TEXT,
    reasons TEXT,
    market_context TEXT,
    meta TEXT,
    exit_price REAL,
    exit_fee REAL,
    exit_reason TEXT,
    exit_detail TEXT,
    pnl REAL,
    pnl_pct REAL,
    r_multiple REAL,
    client_order_id TEXT NOT NULL UNIQUE
);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_position_per_symbol ON positions(symbol) WHERE status = 'open';

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id TEXT NOT NULL UNIQUE,
    position_id INTEGER REFERENCES positions(id),
    mode TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy','sell')),
    quantity REAL NOT NULL,
    reference_price REAL NOT NULL,
    price REAL NOT NULL,
    fee REAL NOT NULL,
    cost REAL NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    bar_ts INTEGER,
    action TEXT NOT NULL,
    strategy TEXT,
    score REAL,
    summary TEXT NOT NULL,
    details TEXT
);
CREATE INDEX IF NOT EXISTS decisions_symbol_ts ON decisions(symbol, ts);

CREATE TABLE IF NOT EXISTS equity (
    ts TEXT NOT NULL,
    cash REAL NOT NULL,
    equity REAL NOT NULL,
    exposure REAL NOT NULL,
    open_positions INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    data TEXT
);

CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    evidence TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposta'
);

CREATE TABLE IF NOT EXISTS watchlist (symbol TEXT PRIMARY KEY, added_at TEXT NOT NULL);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(value: Any) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False, default=str)


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None, timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def execute(self, sql: str, params: tuple = ()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.lastrowid

    # --- stato chiave/valore ----------------------------------------------
    def get_state(self, key: str, default: Any = None) -> Any:
        rows = self.query("SELECT value FROM state WHERE key = ?", (key,))
        return json.loads(rows[0]["value"]) if rows else default

    def set_state(self, key: str, value: Any, conn: sqlite3.Connection | None = None) -> None:
        sql = "INSERT INTO state(key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at"
        params = (key, json.dumps(value, default=str), _now())
        if conn is not None:
            conn.execute(sql, params)
        else:
            self.execute(sql, params)

    # --- eventi, decisioni, equity ----------------------------------------
    def log_event(self, type_: str, message: str, level: str = "INFO", data: Any = None) -> None:
        self.execute(
            "INSERT INTO events(ts, level, type, message, data) VALUES (?, ?, ?, ?, ?)",
            (_now(), level, type_, message, _dumps(data)),
        )

    def record_decision(self, symbol: str, action: str, summary: str, bar_ts: int | None, strategy: str | None, score: float | None, details: Any) -> None:
        self.execute(
            "INSERT INTO decisions(ts, symbol, bar_ts, action, strategy, score, summary, details) VALUES (?,?,?,?,?,?,?,?)",
            (_now(), symbol, bar_ts, action, strategy, score, summary, _dumps(details)),
        )

    def record_equity(self, cash: float, equity: float, exposure: float, open_positions: int) -> None:
        self.execute(
            "INSERT INTO equity(ts, cash, equity, exposure, open_positions) VALUES (?,?,?,?,?)",
            (_now(), cash, equity, exposure, open_positions),
        )

    # --- posizioni --------------------------------------------------------
    def open_positions(self) -> list[dict]:
        return [self._decode(r) for r in self.query("SELECT * FROM positions WHERE status='open' ORDER BY id")]

    def closed_positions(self, limit: int | None = None) -> list[dict]:
        sql = "SELECT * FROM positions WHERE status='closed' ORDER BY closed_at DESC"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [self._decode(r) for r in self.query(sql)]

    def position(self, position_id: int) -> dict | None:
        rows = self.query("SELECT * FROM positions WHERE id = ?", (position_id,))
        return self._decode(rows[0]) if rows else None

    def order_exists(self, client_order_id: str) -> bool:
        return bool(self.query("SELECT 1 FROM orders WHERE client_order_id = ?", (client_order_id,)))

    @staticmethod
    def _decode(row: dict) -> dict:
        for key in ("reasons", "market_context", "meta"):
            if row.get(key):
                row[key] = json.loads(row[key])
        return row

    def update_position(self, position_id: int, **fields: Any) -> None:
        if not fields:
            return
        for key in ("reasons", "market_context", "meta"):
            if key in fields:
                fields[key] = _dumps(fields[key])
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.execute(f"UPDATE positions SET {cols} WHERE id = ?", (*fields.values(), position_id))

    # --- watchlist --------------------------------------------------------
    def watchlist(self) -> list[str]:
        return [r["symbol"] for r in self.query("SELECT symbol FROM watchlist ORDER BY added_at, symbol")]

    def add_watch(self, symbol: str) -> bool:
        before = len(self.watchlist())
        self.execute("INSERT OR IGNORE INTO watchlist(symbol, added_at) VALUES (?, ?)", (symbol, _now()))
        return len(self.watchlist()) > before

    def remove_watch(self, symbol: str) -> bool:
        before = len(self.watchlist())
        self.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
        return len(self.watchlist()) < before
