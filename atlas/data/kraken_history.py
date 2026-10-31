"""Ricostruzione di storici OHLCV lunghi dai trade pubblici di Kraken.

L'endpoint OHLC di Kraken restituisce solo le ultime 720 candele. L'endpoint
pubblico ``Trades`` permette invece di risalire nel tempo: i trade vengono
aggregati in candele del timeframe richiesto (default 1h).

Caratteristiche:
- solo endpoint PUBBLICI, nessuna credenziale;
- riprendibile: un file di checkpoint conserva cursore e candela parziale,
  quindi un'interruzione non fa perdere il lavoro;
- rispetta i limiti di frequenza (pausa minima tra richieste, backoff esponenziale
  sugli errori ``EAPI:Rate limit exceeded`` e di rete);
- le candele senza alcun trade NON vengono inventate: restano buchi che la
  validazione dei dati segnala.

Uso: ``python -m atlas history BTC/EUR --days 365 --out data/history/BTC_EUR_1h.csv``
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from atlas.data.market_data import timeframe_ms
from atlas.logging_setup import get_logger

log = get_logger(__name__)

KRAKEN_PAIRS = {"BTC/EUR": "XBTEUR", "ETH/EUR": "ETHEUR", "SOL/EUR": "SOLEUR", "BTC/USD": "XBTUSD", "ETH/USD": "ETHUSD"}
TRADES_URL = "https://api.kraken.com/0/public/Trades"


def kraken_pair(symbol: str) -> str:
    return KRAKEN_PAIRS.get(symbol.upper(), symbol.upper().replace("/", "").replace("BTC", "XBT"))


@dataclass
class Bar:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    def add(self, price: float, qty: float) -> None:
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += qty

    def row(self) -> list:
        return [self.ts, self.open, self.high, self.low, self.close, round(self.volume, 10)]


class TradeAggregator:
    """Aggrega trade ordinati nel tempo in candele; emette solo candele chiuse."""

    def __init__(self, timeframe: str = "1h", current: Bar | None = None) -> None:
        self.tf = timeframe_ms(timeframe)
        self.current = current

    def add(self, ts_ms: int, price: float, qty: float) -> list[Bar]:
        bucket = ts_ms - ts_ms % self.tf
        closed: list[Bar] = []
        if self.current is None:
            self.current = Bar(bucket, price, price, price, price, 0.0)
        elif bucket > self.current.ts:
            closed.append(self.current)
            self.current = Bar(bucket, price, price, price, price, 0.0)
        elif bucket < self.current.ts:
            return closed  # trade fuori ordine: ignorato (Kraken li restituisce ordinati)
        self.current.add(price, qty)
        return closed


def download_trades_ohlcv(
    symbol: str,
    out: str | Path,
    days: int = 365,
    timeframe: str = "1h",
    min_interval: float = 0.85,
    max_requests: int | None = None,
    fetch: Callable[[dict], dict] | None = None,
    now: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Scarica (o riprende) lo storico e scrive un CSV ATLAS (timestamp ms, OHLCV)."""
    out = Path(out)
    ckpt_path = out.with_suffix(out.suffix + ".ckpt")
    out.parent.mkdir(parents=True, exist_ok=True)

    if fetch is None:
        import requests

        session = requests.Session()

        def fetch(params: dict) -> dict:
            return session.get(TRADES_URL, params=params, timeout=30).json()

    end_ns = int(now() * 1e9)
    if ckpt_path.exists():
        ck = json.loads(ckpt_path.read_text())
        cursor, end_ns = int(ck["cursor"]), int(ck["end_ns"])
        agg = TradeAggregator(timeframe, Bar(**ck["current"]) if ck.get("current") else None)
        mode = "a"
    else:
        cursor = int((now() - days * 86400) * 1e9)
        agg = TradeAggregator(timeframe)
        mode = "w"

    requests_done = rows_written = 0
    backoff = 2.0
    pair = kraken_pair(symbol)
    with out.open(mode, newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if mode == "w":
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        finished = False
        while not finished:
            if max_requests is not None and requests_done >= max_requests:
                break
            started = now()
            try:
                data = fetch({"pair": pair, "since": cursor, "count": 1000})
            except Exception as exc:  # noqa: BLE001 - rete instabile: si riprova
                log.warning("download trade: errore di rete", extra={"data": {"error": type(exc).__name__}})
                sleep(backoff)
                backoff = min(backoff * 2, 120)
                continue
            requests_done += 1
            errors = data.get("error") or []
            if errors:
                if any("Rate limit" in e or "Too many" in e for e in errors):
                    sleep(backoff)
                    backoff = min(backoff * 2, 120)
                    continue
                raise RuntimeError(f"Kraken: {errors}")
            backoff = 2.0
            result = data["result"]
            trades = next(v for k, v in result.items() if k != "last")
            new_cursor = int(result["last"])
            for price, qty, t, *_rest in trades:
                ts_ms = int(float(t) * 1000)
                if ts_ms * 1_000_000 >= end_ns:
                    finished = True
                    break
                for bar in agg.add(ts_ms, float(price), float(qty)):
                    writer.writerow(bar.row())
                    rows_written += 1
            if not trades or new_cursor <= cursor:
                finished = True
            cursor = new_cursor
            fh.flush()
            ckpt_path.write_text(json.dumps({"cursor": cursor, "end_ns": end_ns, "current": agg.current.__dict__ if agg.current else None}))
            elapsed = now() - started
            if elapsed < min_interval:
                sleep(min_interval - elapsed)
    if finished:
        ckpt_path.unlink(missing_ok=True)  # l'ultima candela (parziale) non viene scritta
    return {"symbol": symbol, "requests": requests_done, "rows": rows_written, "finished": finished, "out": str(out)}
