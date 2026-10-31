"""Composizione dell'applicazione e operazioni ad alto livello.

``Atlas`` collega configurazione, database, fonte dati, ciclo di trading e
notifiche. I metodi ``text_*`` restituiscono i testi in italiano usati dai
comandi Telegram (e dalla CLI): il bot si limita a inoltrarli.
"""

from __future__ import annotations

from datetime import datetime, timezone

from atlas import __version__
from atlas.config import Settings, normalize_symbol
from atlas.data.exchange import MarketDataSource
from atlas.engine.cycle import TradingCycle
from atlas.performance.analyzer import generate_proposals, performance_summary
from atlas.storage.db import Database
from atlas.strategy.registry import describe
from atlas.telegram import formatters as fmt
from atlas.telegram.notifier import Notifier, build_notifier


def build_source(settings: Settings) -> MarketDataSource:
    from atlas.data.exchange import KrakenDataSource, LockedSource

    return LockedSource(KrakenDataSource(settings.kraken_api_key, settings.kraken_api_secret, settings.exchange_timeout_ms, settings.exchange_max_retries))


class Atlas:
    def __init__(self, settings: Settings, source: MarketDataSource | None = None, notifier: Notifier | None = None, db: Database | None = None, clock=None) -> None:
        self.settings = settings
        self.db = db or Database(settings.db_path)
        self.source = source or build_source(settings)
        self.notifier = notifier or build_notifier(settings)
        self.cycle = TradingCycle(settings, self.db, self.source, self.notifier, clock=clock)
        self.ccy = "€" if settings.quote_currency == "EUR" else settings.quote_currency

    # --- helper -----------------------------------------------------------
    def _state(self):
        return self.cycle.account.state()

    def _sym(self, raw: str) -> str:
        return normalize_symbol(raw, self.settings.quote_currency)

    # --- informazioni -------------------------------------------------------
    def text_help(self) -> str:
        return "\n".join(
            [
                f"🤖 ATLAS v{__version__} — modalità PAPER TRADING (simulazione)",
                "",
                "ℹ️ Informazioni",
                "/status – stato del sistema",
                "/saldo – capitale simulato (e saldo Kraken se configurato)",
                "/prezzo BTC – prezzo attuale",
                "/watchlist – coppie monitorate (admin: /watchlist add SOL, /watchlist remove SOL)",
                "",
                "🔎 Analisi",
                "/analisi BTC – analisi completa con decisione motivata",
                "/segnali – ultime decisioni prese",
                "/mercato – panoramica della watchlist",
                "/strategie – strategie e versioni",
                "",
                "📊 Trading simulato",
                "/posizioni – posizioni aperte",
                "/operazioni – ultime operazioni chiuse",
                "/performance – statistiche",
                "/report – riepilogo completo e proposte di miglioramento",
                "/rischio – limiti di rischio e stato",
                "",
                "⚙️ Controllo (solo amministratori)",
                "/pausa – sospende le nuove operazioni",
                "/riprendi – riprende (dopo un arresto: /riprendi conferma)",
                "/chiudi BTC – chiude una posizione simulata",
                "/modalita – modalità operativa",
                "/config – configurazione attuale (senza segreti)",
                "",
                "⚠️ ATLAS non garantisce alcun rendimento. Lo score non è una probabilità di profitto.",
            ]
        )

    def text_status(self) -> str:
        st = self._state()
        last = self.db.get_state("last_cycle") or {}
        hb = self.db.get_state("heartbeat")
        status = "🛑 ARRESTO DI SICUREZZA" if st.halted else "⏸ IN PAUSA" if st.paused else "▶️ ATTIVO"
        lines = [
            f"📡 ATLAS — Stato ({status})",
            "",
            "Modalità: PAPER TRADING (nessun ordine reale possibile)",
            f"Ultimo ciclo: {fmt.ts_label(last.get('at'))} — {'OK' if last.get('ok', True) else 'con errori'}",
            f"Heartbeat: {fmt.ts_label(hb)}",
            f"Watchlist: {', '.join(self.db.watchlist()) or 'vuota'}",
            "",
            *fmt.portfolio_summary(st, self.cycle.account.initial_capital, self.ccy),
        ]
        if st.halted:
            lines += ["", f"Motivo arresto: {st.halt_reason}"]
        if last.get("errors"):
            lines += ["", "Ultimi problemi:"] + [f"• {e}" for e in last["errors"][:3]]
        return "\n".join(lines)

    def text_balance(self) -> str:
        st = self._state()
        lines = ["💰 ATLAS — Saldo simulato", "", *fmt.portfolio_summary(st, self.cycle.account.initial_capital, self.ccy)]
        if self.settings.kraken_api_key and hasattr(self.source, "fetch_balance"):
            try:
                bal = self.source.fetch_balance()
                lines += ["", "Saldo reale Kraken (sola lettura):"] + ([f"{k}: {v:.8g}" for k, v in sorted(bal.items())] or ["nessun fondo"])
            except Exception as exc:  # noqa: BLE001
                lines += ["", f"Saldo Kraken non disponibile ({type(exc).__name__})."]
        return "\n".join(lines)

    def text_price(self, raw: str) -> str:
        sym = self._sym(raw)
        t = self.cycle.market.ticker(sym)
        return "\n".join(
            [
                f"💶 {sym}",
                f"Ultimo: {fmt.price(t['last'])}",
                f"Denaro/Lettera: {fmt.price(t['bid'])} / {fmt.price(t['ask'])}" + (f" (spread {fmt.num(t['spread_pct'], 3)}%)" if t["spread_pct"] is not None else ""),
                f"Variazione 24h: {fmt.signed_pct(t['change_pct'])}",
            ]
        )

    def text_watchlist(self, args: list[str], is_admin: bool) -> str:
        if args and args[0].lower() in {"add", "aggiungi", "remove", "rimuovi"}:
            if not is_admin:
                return "⛔ Solo gli amministratori possono modificare la watchlist."
            if len(args) < 2:
                return "Uso: /watchlist add SOL oppure /watchlist remove SOL"
            sym = self._sym(args[1])
            if args[0].lower() in {"add", "aggiungi"}:
                try:
                    self.source.market_rules(sym)
                except Exception:  # noqa: BLE001
                    return f"❌ {sym} non risulta disponibile su Kraken."
                return f"✅ {sym} aggiunta." if self.db.add_watch(sym) else f"{sym} è già presente."
            return f"✅ {sym} rimossa." if self.db.remove_watch(sym) else f"{sym} non era presente."
        wl = self.db.watchlist()
        return "👀 Watchlist\n\n" + ("\n".join(f"• {s}" for s in wl) if wl else "vuota")

    # --- analisi -----------------------------------------------------------
    def text_analysis(self, raw: str) -> str:
        sym = self._sym(raw)
        market = self.cycle._market_reference()
        a = self.cycle.analyzer.analyze(sym, market)
        st = self._state()
        decision = self.cycle.engine.decide_entry(a.ctx, st, self.source.market_rules(sym), self.cycle.clock())
        return fmt.analysis_message(a.ctx, decision) + "\n\n(Analisi su richiesta: nessuna operazione viene eseguita da questo comando.)"

    def text_signals(self, limit: int = 8) -> str:
        rows = self.db.query("SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (limit,))
        if not rows:
            return "Nessuna decisione registrata finora."
        lines = ["🧭 Ultime decisioni", ""]
        for r in rows:
            icon = "🟢" if r["action"] == "ENTER" else "⚪️"
            score = f" — score {r['score']:.0f}" if r["score"] is not None else ""
            lines.append(f"{icon} {r['symbol']} · {fmt.ts_label(r['bar_ts'])}{score}\n   {r['summary']}")
        return "\n".join(lines)

    def text_market(self) -> str:
        market = self.cycle._market_reference()
        lines = ["🌍 Panoramica di mercato", ""]
        if market:
            lines.append(f"Riferimento {self.settings.market_reference} ({market.timeframe}): {fmt.TREND_IT[market.trend]}")
            lines.append("")
        for sym in self.db.watchlist():
            try:
                a = self.cycle.analyzer.analyze(sym, market)
                p = a.ctx.primary
                lines.append(f"{sym}: {fmt.price(p.close)} · {fmt.TREND_IT[p.trend]} · RSI {p.rsi:.0f} · {fmt.REGIME_IT.get(p.regime, p.regime)}")
            except Exception as exc:  # noqa: BLE001
                lines.append(f"{sym}: dati non disponibili ({type(exc).__name__})")
        return "\n".join(lines)

    def text_strategies(self) -> str:
        active = set(self.settings.strategies)
        lines = ["🧠 Strategie", ""]
        for d in describe():
            flag = "✅ attiva" if d["name"] in active else "⏹ non attiva"
            lines.append(f"{d['name']} v{d['version']} — {flag}, stato: {d['status']}\n   {d['description']}")
        lines.append("\nNessuna strategia è considerata validata finché non supera il walk-forward su dati reali (docs/STRATEGIES.md).")
        return "\n".join(lines)

    # --- trading -----------------------------------------------------------
    def text_positions(self) -> str:
        positions = self.db.open_positions()
        if not positions:
            return "Nessuna posizione aperta. ATLAS attende condizioni adeguate."
        last = self.db.get_state("last_prices", {}) or {}
        lines = ["📂 Posizioni simulate aperte", ""]
        for p in positions:
            cur = last.get(p["symbol"], p["entry_price"])
            pnl = (cur - p["entry_price"]) * p["quantity"] - p["entry_fee"]
            lines += [
                f"{p['symbol']} ({p['strategy']}) dal {fmt.ts_label(p['opened_at'])}",
                f"  Ingresso {fmt.price(p['entry_price'])} · attuale {fmt.price(cur)} · {fmt.money(pnl, self.ccy)}",
                f"  Stop {fmt.price(p['stop_loss'])}{' (trailing)' if p['trailing_active'] else ''} · Target {fmt.price(p['take_profit'])} · Score {p['score']:.0f}",
            ]
        return "\n".join(lines)

    def text_trades(self, limit: int = 10) -> str:
        rows = self.db.closed_positions(limit)
        if not rows:
            return "Nessuna operazione chiusa finora."
        lines = ["📜 Ultime operazioni chiuse", ""]
        for p in rows:
            icon = "✅" if p["pnl"] > 0 else "🔴"
            lines.append(f"{icon} {p['symbol']} {fmt.money(p['pnl'], self.ccy)} ({fmt.num(p['r_multiple'])} R) · {p['exit_reason']} · {fmt.ts_label(p['closed_at'])}")
        return "\n".join(lines)

    def text_performance(self) -> str:
        s = performance_summary(self.db)
        o = s["overall"]
        if not o.get("trades"):
            return "📊 Nessuna operazione chiusa: statistiche non ancora disponibili."
        lines = [
            "📊 Performance paper trading",
            "",
            f"Operazioni: {o['trades']}   Win rate: {fmt.num(o['win_rate'], 1)}%",
            f"Risultato netto: {fmt.money(o['net_pnl'], self.ccy)}   Profit factor: {fmt.num(o['profit_factor'])}",
            f"Media vincita/perdita: {fmt.money(o['avg_win'], self.ccy)} / {fmt.money(o['avg_loss'], self.ccy)}",
            f"Expectancy: {fmt.money(o['expectancy'], self.ccy)} ({fmt.num(o['expectancy_r'])} R) per operazione",
            f"Commissioni pagate: {fmt.money(s.get('fees_total'), self.ccy)}",
            f"Drawdown massimo: {fmt.num(s['max_drawdown_pct'])}%",
        ]
        if not o["significant"]:
            lines.append(f"\n⚠️ Campione ridotto ({o['trades']} operazioni): risultati non statisticamente significativi.")
        if s["by_strategy"]:
            lines.append("\nPer strategia:")
            lines += [f"• {k}: {m['trades']} op., {fmt.money(m['net_pnl'], self.ccy)}, {fmt.num(m['expectancy_r'])} R" for k, m in s["by_strategy"].items()]
        return "\n".join(lines)

    def text_report(self) -> str:
        perf = self.text_performance()
        props = generate_proposals(self.db)
        lines = [self.text_status(), "", perf, "", "💡 Proposte (da validare con backtest, mai applicate automaticamente):"]
        lines += [f"• {p['title']}" for p in props] or ["• nessuna"]
        return "\n".join(lines)

    def text_risk(self) -> str:
        L = self.cycle.limits
        st = self._state()
        blocks = self.cycle.risk.portfolio_blocks(st, self.cycle.clock())
        lines = [
            "🛡 Gestione del rischio",
            "",
            f"Rischio per operazione: {L.risk_per_trade_pct}% del capitale",
            f"Rapporto rendimento/rischio minimo (netto costi): {L.min_reward_risk}",
            f"Posizioni contemporanee max: {L.max_open_positions}",
            f"Dimensione max per posizione: {L.max_position_pct}%   Esposizione max: {L.max_exposure_pct}%",
            f"Perdita giornaliera max: {L.max_daily_loss_pct}%   Drawdown max: {L.max_drawdown_pct}% (arresto)",
            f"Pausa dopo {L.max_consecutive_losses} perdite consecutive: {L.cooldown_hours_after_losses}h",
            f"Rischio max su asset correlati: {L.max_correlated_risk_pct}% (correlazione ≥ {L.correlation_threshold})",
            f"Costi simulati: commissione {self.settings.taker_fee_pct}% + slippage {self.settings.slippage_pct}% per lato, più spread",
            "",
            f"Oggi: {fmt.signed_pct(st.daily_pnl_pct)}   Drawdown: {fmt.num(st.drawdown_pct)}%   Perdite consecutive: {st.consecutive_losses}",
            "",
            "Blocchi attivi:" if blocks else "Nessun blocco attivo.",
        ]
        lines += [f"• {b}" for b in blocks]
        return "\n".join(lines)

    # --- controllo ---------------------------------------------------------
    def pause(self) -> str:
        self.cycle.account.set_paused(True)
        return "⏸ Nuove operazioni sospese. Le posizioni aperte continuano a essere gestite."

    def resume(self, args: list[str]) -> str:
        st = self._state()
        if st.halted:
            if not args or args[0].lower() != "conferma":
                return f"🛑 ATLAS è in arresto di sicurezza: {st.halt_reason}\nVerifica la situazione, poi invia /riprendi conferma"
            reset_peak = "drawdown" in (st.halt_reason or "")
            self.cycle.account.clear_halt(reset_peak=reset_peak)
        self.cycle.account.set_paused(False)
        return "▶️ Operatività ripresa." + (" Il riferimento del drawdown è stato azzerato al capitale attuale." if st.halted and "drawdown" in (st.halt_reason or "") else "")

    def close(self, raw: str) -> str:
        sym = self._sym(raw)
        closed = self.cycle.close_manually(sym)
        if not closed:
            return f"Nessuna posizione aperta su {sym}."
        return fmt.closed_message(closed)

    def text_mode(self) -> str:
        return (
            "⚙️ Modalità: PAPER TRADING\n\n"
            "Tutte le operazioni sono simulate con capitale virtuale.\n"
            "Il trading reale NON è attivabile da Telegram né da configurazione in questa versione: "
            "richiede l'autorizzazione esplicita e la procedura descritta in docs/LIVE_TRADING_POLICY.md."
        )

    def text_config(self) -> str:
        cfg = self.settings.redacted()
        keys = [
            "mode", "watchlist", "timeframe", "higher_timeframe", "strategies", "min_score", "min_reward_risk",
            "initial_capital", "taker_fee_pct", "slippage_pct", "risk_per_trade_pct", "max_open_positions",
            "max_daily_loss_pct", "max_drawdown_pct", "cycle_interval_seconds", "telegram_token", "kraken_api_key",
        ]
        return "🔧 Configurazione (modificabile solo tramite variabili d'ambiente + riavvio)\n\n" + "\n".join(f"{k}: {cfg[k]}" for k in keys)
