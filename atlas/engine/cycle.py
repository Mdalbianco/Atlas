"""Ciclo operativo di ATLAS (paper trading).

Ogni ciclo:
 1. verifica la disponibilità dell'exchange (health check);
 2. scarica e valida i dati della watchlist;
 3. analizza il mercato (multi-timeframe + riferimento generale);
 4. gestisce le posizioni aperte (stop/target intrabar, trailing, invalidazione);
 5. aggiorna il portafoglio e verifica i limiti globali (arresti di sicurezza);
 6. cerca nuove opportunità SOLO alla chiusura di una nuova candela;
 7. applica il risk manager ed esegue le operazioni simulate;
 8. registra decisioni, equity, heartbeat e invia le notifiche.

Ripresa dopo riavvio: tutto lo stato è in SQLite. Una candela già valutata
non viene rivalutata (``last_eval_bar``) e un segnale già eseguito non può
essere rieseguito (client_order_id univoco).
"""

from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone

from atlas.analysis.snapshot import Snapshot, build_snapshot
from atlas.data.exchange import ExchangeUnavailable, MarketDataSource
from atlas.data.market_data import DataQualityError, MarketDataService
from atlas.domain import Action, ExitReason
from atlas.engine.account import PaperAccount
from atlas.engine.analyzer import Analyzer, SymbolAnalysis, correlations
from atlas.engine.decision import DecisionEngine
from atlas.engine.position_manager import ManagementParams, check_stop_target, on_bar_close
from atlas.execution.paper import OrderRejected, PaperBroker
from atlas.logging_setup import get_logger
from atlas.risk.costs import CostModel
from atlas.risk.manager import RiskLimits, RiskManager
from atlas.scoring import ScoreEngine
from atlas.storage.db import Database
from atlas.strategy.registry import build_strategies
from atlas.telegram import formatters as fmt
from atlas.telegram.notifier import Notifier

log = get_logger(__name__)


@dataclass
class CycleReport:
    started_at: datetime
    ok: bool = True
    analyzed: list[str] = field(default_factory=list)
    opened: list[dict] = field(default_factory=list)
    closed: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    equity: float | None = None


class TradingCycle:
    def __init__(self, settings, db: Database, source: MarketDataSource, notifier: Notifier, clock=None) -> None:
        self.s = settings
        self.db = db
        self.source = source
        self.notifier = notifier
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.market = MarketDataService(source, settings.max_data_age_minutes, clock=lambda: int(self.clock().timestamp() * 1000))
        self.analyzer = Analyzer(self.market, settings.timeframe, settings.higher_timeframe, settings.candles_limit, settings.max_bar_move_atr)
        self.costs = CostModel(settings.taker_fee_pct, settings.slippage_pct, settings.default_spread_pct)
        self.limits = RiskLimits.from_settings(settings)
        self.risk = RiskManager(self.limits, self.costs)
        self.strategies = {st.name: st for st in build_strategies(settings.strategies)}
        self.engine = DecisionEngine(list(self.strategies.values()), ScoreEngine(self.costs, settings.min_reward_risk), self.risk, settings.min_score)
        self.account = PaperAccount(db, PaperBroker(self.costs), settings.initial_capital, clock=self.clock)
        self.lock = threading.RLock()  # un solo ciclo / chiusura manuale alla volta
        self.mgmt = ManagementParams(settings.trailing_activation_r, settings.trailing_atr_multiple, settings.time_stop_bars)
        if not db.watchlist() and db.get_state("watchlist_seeded") is None:
            for sym in settings.watchlist:
                db.add_watch(sym)
            db.set_state("watchlist_seeded", True)

    # ------------------------------------------------------------------
    def _notify(self, text: str) -> None:
        try:
            self.notifier.send(text)
        except Exception:  # noqa: BLE001
            log.exception("invio notifica fallito")

    def run_once(self) -> CycleReport:
        with self.lock:
            return self._run_once_locked()

    def _run_once_locked(self) -> CycleReport:
        now = self.clock()
        rep = CycleReport(started_at=now)
        try:
            self._run(rep, now)
            self.db.set_state("consecutive_errors", 0)
        except Exception as exc:  # errore imprevisto: possibile problema critico
            rep.ok = False
            rep.errors.append(f"{type(exc).__name__}: {exc}")
            log.error("ciclo fallito", extra={"data": {"error": str(exc), "trace": traceback.format_exc()[-2000:]}})
            self._on_cycle_error(f"{type(exc).__name__}: {exc}", critical=not isinstance(exc, (ExchangeUnavailable, DataQualityError)))
        finally:
            self.db.set_state("last_cycle", {"at": now.isoformat(), "ok": rep.ok, "errors": rep.errors[-5:], "opened": len(rep.opened), "closed": len(rep.closed)})
            self.db.set_state("heartbeat", self.clock().isoformat())
        return rep

    def _on_cycle_error(self, detail: str, critical: bool) -> None:
        n = int(self.db.get_state("consecutive_errors", 0)) + 1
        self.db.set_state("consecutive_errors", n)
        self.db.log_event("cycle_error", detail, level="ERROR", data={"consecutive": n})
        if critical and not self.db.get_state("halted", False):
            self.account.halt(f"errore critico: {detail[:200]}")
            self._notify(fmt.halt_message(f"errore critico imprevisto ({detail[:200]})"))
        elif n == self.s.max_consecutive_errors:
            self._notify(fmt.error_message(f"{n} cicli consecutivi falliti.", detail[:300]))

    def _run(self, rep: CycleReport, now: datetime) -> None:
        if not self.source.ping():
            raise ExchangeUnavailable("exchange non raggiungibile (health check fallito)")

        watch = self.db.watchlist()
        open_positions = {p["symbol"]: p for p in self.db.open_positions()}
        symbols = list(dict.fromkeys(watch + list(open_positions)))

        market_snap = self._market_reference()
        analyses: dict[str, SymbolAnalysis] = {}
        for sym in symbols:
            try:
                analyses[sym] = self.analyzer.analyze(sym, market_snap)
                rep.analyzed.append(sym)
            except (ExchangeUnavailable, DataQualityError, ValueError) as exc:
                rep.errors.append(f"{sym}: {exc}")
                self.db.log_event("data_error", f"{sym}: {exc}", level="WARNING")

        # --- gestione posizioni aperte ----------------------------------
        for sym, pos in open_positions.items():
            a = analyses.get(sym)
            try:
                closed = self._manage_position(pos, a, now)
                if closed:
                    rep.closed.append(closed)
                    self._notify(fmt.closed_message(closed))
            except (ExchangeUnavailable, DataQualityError) as exc:
                rep.errors.append(f"gestione {sym}: {exc}")

        prices = {sym: a.ticker["last"] for sym, a in analyses.items()}
        state = self.account.mark_to_market(prices)
        rep.equity = state.equity
        self.db.record_equity(state.cash, state.equity, state.exposure, len(state.positions))

        halt = self.risk.should_halt(state)
        if halt and not state.halted:
            self.account.halt(halt)
            self._notify(fmt.halt_message(halt))
            state = self.account.state(prices)

        blocks = self.risk.portfolio_blocks(state, now)
        rep.blocks = blocks
        self._notify_block_change(blocks)

        # --- nuove opportunità -------------------------------------------
        last_eval = self.db.get_state("last_eval_bar", {}) or {}
        frames = {sym: a.primary_df for sym, a in analyses.items()}
        for sym in watch:
            a = analyses.get(sym)
            if a is None or sym in {p.symbol for p in state.positions}:
                continue
            bar_ts = a.ctx.primary.timestamp
            if last_eval.get(sym) == bar_ts:
                continue  # candela già valutata
            rules = self.source.market_rules(sym)
            corr = correlations(a.primary_df, {p.symbol: frames[p.symbol] for p in state.positions if p.symbol in frames})
            decision = self.engine.decide_entry(a.ctx, state, rules, now, correlations=corr)
            last_eval[sym] = bar_ts
            self.db.record_decision(sym, decision.action.value, decision.summary, bar_ts, decision.strategy, decision.score.score if decision.score else None, decision.to_dict())
            rep.decisions.append({"symbol": sym, "action": decision.action.value, "summary": decision.summary})
            if decision.action is Action.ENTER:
                ticker = a.ticker
                try:
                    position = self.account.open_position(
                        decision.signal, decision.risk, decision.score, rules,
                        reference_price=ticker["last"], spread_pct=ticker.get("spread_pct"),
                        market_context={"primary": a.ctx.primary.to_dict(), "higher": a.ctx.higher.to_dict() if a.ctx.higher else None, "market_condition": a.ctx.market_condition},
                        now=now,
                    )
                except OrderRejected as exc:
                    self.db.log_event("order_rejected", f"{sym}: {exc}", level="WARNING")
                    rep.errors.append(f"{sym}: ordine rifiutato ({exc})")
                    continue
                if position:
                    rep.opened.append(position)
                    self._notify(fmt.opened_message(position, decision, a.ctx))
                    state = self.account.state(prices)
        self.db.set_state("last_eval_bar", last_eval)

    def _market_reference(self) -> Snapshot | None:
        try:
            snap, _, _ = self.analyzer.snapshot(self.s.market_reference, self.s.higher_timeframe)
            return snap
        except Exception as exc:  # noqa: BLE001 - il riferimento è facoltativo
            log.warning("riferimento di mercato non disponibile", extra={"data": {"error": str(exc)}})
            return None

    def _notify_block_change(self, blocks: list[str]) -> None:
        key = "|".join(sorted(b.split(" (")[0] for b in blocks if not b.startswith("numero massimo")))
        if key != (self.db.get_state("last_block_key") or ""):
            self.db.set_state("last_block_key", key)
            if key:
                self._notify(fmt.blocked_message("\n".join(f"• {b}" for b in blocks)))

    # ------------------------------------------------------------------
    def _manage_position(self, pos: dict, analysis: SymbolAnalysis | None, now: datetime) -> dict | None:
        sym = pos["symbol"]
        # 1) stop/target sulle candele a 5 minuti successive all'apertura (intrabar)
        opened_ms = int(datetime.fromisoformat(pos["opened_at"]).timestamp() * 1000)
        checked_ms = int((pos.get("meta") or {}).get("intrabar_checked_ms", opened_ms))
        rows = self.source.fetch_ohlcv(sym, "5m", 60)
        spread = analysis.ticker.get("spread_pct") if analysis else None
        last_ts = checked_ms
        for ts, o, h, l, c, _v in rows:
            if ts < checked_ms - 300_000 or ts < opened_ms - 300_000:
                continue
            if ts < opened_ms:  # candela in cui è avvenuto l'ingresso: usa solo la parte successiva (prudente: chiusura)
                o = h = l = c
            ex = check_stop_target(pos, float(o), float(h), float(l))
            if ex:
                return self.account.close_position(pos, ex.reference_price, ex.reason, ex.detail, spread, now)
            last_ts = max(last_ts, int(ts))
        if analysis is None:
            return None
        ticker_last = analysis.ticker["last"]
        ex = check_stop_target(pos, ticker_last, ticker_last, ticker_last)
        if ex:
            return self.account.close_position(pos, ticker_last, ex.reason, ex.detail, spread, now)

        meta = dict(pos.get("meta") or {})
        meta["intrabar_checked_ms"] = last_ts
        updates: dict = {"meta": meta}

        # 2) gestione alla chiusura di nuove candele del timeframe operativo
        df = analysis.primary_df
        new_bars = df[df["timestamp"] > int(pos.get("last_bar_ts") or 0)]
        exit_signal = None
        work = dict(pos)
        for idx in new_bars.index:
            view = df.loc[:idx]
            if len(view) < 210:
                continue
            snap = build_snapshot(sym, self.s.timeframe, view, self.s.max_bar_move_atr, enriched=view)
            upd, ex = on_bar_close(work, snap, float(df.at[idx, "high"]), self.strategies.get(pos["strategy"]), self.mgmt)
            work.update(upd)
            updates.update(upd)
            if ex:
                exit_signal = ex
                break
        self.db.update_position(pos["id"], **updates)
        if exit_signal:
            fresh = self.db.position(pos["id"])
            return self.account.close_position(fresh, ticker_last, exit_signal.reason, exit_signal.detail, spread, now)
        return None

    # ------------------------------------------------------------------
    def close_manually(self, symbol: str) -> dict | None:
        with self.lock:
            return self._close_manually(symbol)

    def _close_manually(self, symbol: str) -> dict | None:
        pos = next((p for p in self.db.open_positions() if p["symbol"] == symbol), None)
        if pos is None:
            return None
        t = self.market.ticker(symbol)
        return self.account.close_position(pos, t["last"], ExitReason.MANUAL, "chiusura richiesta dall'utente", t.get("spread_pct"), self.clock())

