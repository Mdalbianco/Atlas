"""Analisi dello storico operativo e proposte di miglioramento.

Le proposte sono DATI (tabella ``proposals``), mai modifiche automatiche:
ogni proposta riporta l'evidenza numerica che l'ha generata e va validata con
un backtest walk-forward prima di essere eventualmente adottata da una persona,
creando una nuova versione della strategia.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from atlas.backtest.metrics import MIN_TRADES_FOR_SIGNIFICANCE, group_metrics, max_drawdown, score_buckets, trade_metrics
from atlas.storage.db import Database

MIN_GROUP_TRADES = 8


def closed_trades_frame(db: Database) -> pd.DataFrame:
    rows = db.closed_positions()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["fees"] = df["entry_fee"].fillna(0) + df["exit_fee"].fillna(0)
    df["regime"] = df["market_context"].apply(lambda c: (c or {}).get("primary", {}).get("regime") if isinstance(c, dict) else None)
    df["opened_at"] = pd.to_datetime(df["opened_at"], utc=True, format="ISO8601")
    df["closed_at"] = pd.to_datetime(df["closed_at"], utc=True, format="ISO8601")
    df["hours_held"] = (df["closed_at"] - df["opened_at"]).dt.total_seconds() / 3600
    df["expected_rr"] = None
    return df.sort_values("closed_at")


def performance_summary(db: Database) -> dict:
    df = closed_trades_frame(db)
    eq_rows = db.query("SELECT ts, equity FROM equity ORDER BY ts")
    eq = pd.Series([r["equity"] for r in eq_rows], dtype=float)
    dd, _ = max_drawdown(eq) if len(eq) else (0.0, 0)
    out = {
        "overall": trade_metrics(df) if not df.empty else {"trades": 0},
        "by_strategy": group_metrics(df, "strategy"),
        "by_symbol": group_metrics(df, "symbol"),
        "by_regime": group_metrics(df, "regime"),
        "by_exit_reason": group_metrics(df, "exit_reason"),
        "by_score": score_buckets(df) if not df.empty else {},
        "max_drawdown_pct": dd,
    }
    if not df.empty:
        gross = df["pnl"] + df["fees"]
        out["fees_total"] = float(df["fees"].sum())
        out["gross_pnl"] = float(gross.sum())
        out["fees_share_of_gross"] = float(df["fees"].sum() / gross.abs().sum()) if gross.abs().sum() else None
        days = max(1.0, (df["closed_at"].max() - df["opened_at"].min()).total_seconds() / 86400)
        out["trades_per_week"] = float(len(df) / days * 7)
        losing = df[df["pnl"] <= 0]
        out["avg_loss_r"] = float(losing["r_multiple"].mean()) if len(losing) else None
    return out


def generate_proposals(db: Database, save: bool = True) -> list[dict]:
    """Regole esplicite che individuano punti deboli e propongono verifiche."""
    df = closed_trades_frame(db)
    props: list[dict] = []
    if df.empty or len(df) < MIN_GROUP_TRADES:
        return [{"kind": "dati_insufficienti", "title": f"Servono almeno {MIN_GROUP_TRADES} operazioni chiuse per analisi affidabili", "evidence": {"trades": int(len(df))}}]

    for col, label in (("strategy", "strategia"), ("symbol", "asset"), ("regime", "regime di mercato")):
        for key, m in group_metrics(df, col).items():
            if m["trades"] >= MIN_GROUP_TRADES and (m["expectancy_r"] or 0) < -0.1:
                props.append({
                    "kind": f"escludere_{col}",
                    "title": f"Valutare l'esclusione/revisione per {label} '{key}': expectancy {m['expectancy_r']:.2f} R su {m['trades']} operazioni",
                    "evidence": m,
                })

    buckets = score_buckets(df)
    low = buckets.get("55-64") or buckets.get("0-54")
    high = buckets.get("75-100")
    if low and high and low["trades"] >= MIN_GROUP_TRADES and high["trades"] >= MIN_GROUP_TRADES:
        if (low["expectancy_r"] or 0) < 0 < (high["expectancy_r"] or 0):
            props.append({"kind": "alzare_soglia", "title": "Le fasce di score basse perdono mentre le alte guadagnano: testare una soglia minima più alta", "evidence": {"bassa": low, "alta": high}})
        elif (high["expectancy_r"] or 0) <= (low["expectancy_r"] or 0):
            props.append({"kind": "rivedere_pesi", "title": "Lo score non discrimina: le fasce alte non rendono più delle basse. Rivedere i pesi dello scoring", "evidence": {"bassa": low, "alta": high}})

    gross = df["pnl"] + df["fees"]
    if gross.sum() > 0 and df["pnl"].sum() <= 0:
        props.append({"kind": "costi", "title": "Le operazioni sarebbero in utile prima dei costi ma sono in perdita dopo: ridurre la frequenza o puntare a movimenti più ampi", "evidence": {"lordo": float(gross.sum()), "netto": float(df["pnl"].sum()), "commissioni": float(df["fees"].sum())}})

    days = max(1.0, (df["closed_at"].max() - df["opened_at"].min()).total_seconds() / 86400)
    per_week = len(df) / days * 7
    if per_week > 10:
        props.append({"kind": "frequenza", "title": f"Frequenza elevata ({per_week:.1f} operazioni/settimana): valutare filtri più selettivi", "evidence": {"per_week": per_week}})

    exits = group_metrics(df, "exit_reason")
    ts = exits.get("time_stop")
    if ts and ts["trades"] >= MIN_GROUP_TRADES and ts["trades"] / len(df) > 0.3:
        props.append({"kind": "time_stop", "title": "Oltre il 30% delle operazioni chiude per tempo: i segnali potrebbero essere deboli o il target troppo lontano", "evidence": ts})

    if len(df) < MIN_TRADES_FOR_SIGNIFICANCE:
        for p in props:
            p["title"] += f" (campione di {len(df)} operazioni: indicazione preliminare)"

    if save:
        now = datetime.now(timezone.utc).isoformat()
        existing = {r["title"] for r in db.query("SELECT title FROM proposals WHERE status = 'proposta'")}
        for p in props:
            if p["title"] not in existing:
                db.execute("INSERT INTO proposals(ts, kind, title, evidence) VALUES (?, ?, ?, ?)", (now, p["kind"], p["title"], json.dumps(p["evidence"], default=str)))
    return props
