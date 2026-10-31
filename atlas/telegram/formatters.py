"""Testi dei messaggi Telegram, in italiano semplice. Funzioni pure."""

from __future__ import annotations

from datetime import datetime, timezone

from atlas.analysis.snapshot import MarketContext
from atlas.domain import EXIT_REASON_IT, Decision, ExitReason

DISCLAIMER = "Operazione SIMULATA (paper trading): nessun denaro reale è stato usato."

TREND_IT = {"rialzista": "Rialzista 📈", "ribassista": "Ribassista 📉", "laterale": "Laterale ↔️"}
REGIME_IT = {
    "trend_rialzista": "Trend rialzista",
    "trend_ribassista": "Trend ribassista",
    "laterale": "Mercato laterale",
    "alta_volatilita": "Volatilità elevata",
}


def num(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/d"
    s = f"{value:,.{digits}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def price(value: float | None) -> str:
    if value is None:
        return "n/d"
    digits = 2 if value >= 100 else 4 if value >= 1 else 6
    return num(value, digits)


def money(value: float | None, ccy: str = "€") -> str:
    return f"{num(value)} {ccy}"


def signed_pct(value: float | None) -> str:
    return "n/d" if value is None else ("+" if value >= 0 else "") + num(value) + "%"


def ts_label(ts: str | int | datetime | None) -> str:
    if ts is None:
        return "n/d"
    if isinstance(ts, (int, float)):
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    elif isinstance(ts, str):
        dt = datetime.fromisoformat(ts)
    else:
        dt = ts
    return dt.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")


def analysis_message(ctx: MarketContext, decision: Decision | None = None) -> str:
    p, h = ctx.primary, ctx.higher
    s = p.structure
    lines = [
        f"🔎 ATLAS — Analisi {ctx.symbol}",
        "",
        f"Prezzo: {price(p.close)}",
        f"Trend {p.timeframe}: {TREND_IT[p.trend]} (forza ADX {p.adx:.0f})",
    ]
    if h:
        lines.append(f"Trend {h.timeframe}: {TREND_IT[h.trend]}")
    lines += [
        f"Regime: {REGIME_IT.get(p.regime, p.regime)}",
        f"RSI: {p.rsi:.0f}   MACD: {p.momentum}",
        f"Volatilità (ATR): {num(p.atr_pct)}%   Volume: {p.volume_state} (x{num(p.rel_volume, 1)})",
        f"Struttura: {s.structure}" + (" · breakout" if s.breakout else "") + (" · consolidamento" if s.consolidation else ""),
        f"Supporto: {price(s.nearest_support)}   Resistenza: {price(s.nearest_resistance)}",
    ]
    if p.anomaly:
        lines.append(f"⚠️ Anomalia: {p.anomaly_reason}")
    if decision is not None:
        lines += ["", decision_block(decision)]
    return "\n".join(lines)


def decision_block(d: Decision) -> str:
    lines = []
    if d.score is not None:
        lines.append(f"Score: {d.score.score:.0f}/100 — {d.score.category}")
    if d.risk is not None and d.risk.net_reward_risk:
        lines.append(f"Rapporto rischio/rendimento (netto costi): {num(d.risk.net_reward_risk)}")
        if d.risk.approved:
            lines.append(f"Rischio stimato: {num(d.risk.risk_pct)}% del capitale")
    lines.append(f"Decisione: {d.summary}")
    if d.reasons:
        lines.append("Motivazione:")
        lines += [f"• {r}" for r in d.reasons[:6]]
    if d.signal is not None and d.signal.invalidation and d.action.value == "ENTER":
        lines.append("Il segnale è invalidato da:")
        lines += [f"• {r}" for r in d.signal.invalidation[:3]]
    lines.append("ℹ️ Lo score misura la qualità del setup secondo il modello, NON la probabilità di profitto.")
    return "\n".join(lines)


def opened_message(position: dict, decision: Decision, ctx: MarketContext) -> str:
    p = ctx.primary
    risk = decision.risk
    return "\n".join(
        [
            "🟢 ATLAS — Posizione simulata aperta",
            "",
            f"Asset: {position['symbol']}",
            f"Strategia: {position['strategy']} v{position['strategy_version']}",
            f"Trend: {TREND_IT[p.trend]}   RSI: {p.rsi:.0f}   MACD: {p.momentum}",
            f"Score: {decision.score.score:.0f}/100",
            f"Rapporto rischio/rendimento (netto): {num(risk.net_reward_risk)}",
            f"Rischio stimato: {num(risk.risk_pct)}% del capitale",
            "",
            f"Prezzo di ingresso: {price(position['entry_price'])}",
            f"Quantità: {position['quantity']:.8g}  (controvalore {money(position['entry_price'] * position['quantity'])})",
            f"Stop loss: {price(position['stop_loss'])}",
            f"Take profit: {price(position['take_profit'])}",
            f"Commissione: {money(position['entry_fee'])}",
            "",
            "Motivazione: " + "; ".join(decision.signal.reasons[:4]),
            "",
            DISCLAIMER,
        ]
    )


def closed_message(pos: dict) -> str:
    reason = EXIT_REASON_IT.get(ExitReason(pos["exit_reason"]), pos["exit_reason"])
    icon = "✅" if (pos.get("pnl") or 0) > 0 else "🔴"
    return "\n".join(
        [
            f"{icon} ATLAS — Posizione simulata chiusa",
            "",
            f"Asset: {pos['symbol']}  ({pos['strategy']})",
            f"Motivo: {reason}" + (f" — {pos['exit_detail']}" if pos.get("exit_detail") and pos["exit_detail"] != reason else ""),
            f"Ingresso: {price(pos['entry_price'])} → Uscita: {price(pos['exit_price'])}",
            f"Risultato: {money(pos['pnl'])} ({signed_pct(pos['pnl_pct'])}, {num(pos['r_multiple'])} R)",
            f"Commissioni totali: {money((pos.get('entry_fee') or 0) + (pos.get('exit_fee') or 0))}",
            f"Durata: {duration(pos.get('opened_at'), pos.get('closed_at'))}",
            "",
            DISCLAIMER,
        ]
    )


def duration(start: str | None, end: str | None) -> str:
    if not start or not end:
        return "n/d"
    secs = int((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    return (f"{d}g " if d else "") + f"{h}h {m}m"


def blocked_message(reason: str) -> str:
    return f"⛔ ATLAS — Blocco di sicurezza\n\n{reason}\n\nNessuna nuova operazione verrà aperta finché la condizione persiste."


def halt_message(reason: str) -> str:
    return (
        "🛑 ATLAS — ARRESTO DI SICUREZZA\n\n"
        f"Motivo: {reason}\n\n"
        "Le posizioni aperte continuano a essere gestite (stop e target), ma non ne verranno aperte di nuove.\n"
        "Per riprendere dopo aver verificato la situazione: /riprendi conferma"
    )


def error_message(context: str, detail: str) -> str:
    return f"⚠️ ATLAS — Problema rilevato\n\n{context}\nDettaglio: {detail}\n\nATLAS riproverà automaticamente al prossimo ciclo."


def portfolio_summary(st, initial: float, ccy: str = "€") -> list[str]:
    total_ret = (st.equity / initial - 1) * 100 if initial else 0.0
    return [
        f"Capitale totale: {money(st.equity, ccy)} ({signed_pct(total_ret)} dall'inizio)",
        f"Liquidità: {money(st.cash, ccy)}",
        f"Investito: {money(st.exposure, ccy)} in {len(st.positions)} posizioni",
        f"Oggi: {signed_pct(st.daily_pnl_pct)}   Drawdown dal massimo: {num(st.drawdown_pct)}%",
    ]
