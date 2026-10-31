"""Conto di paper trading persistente (SQLite).

Tutte le modifiche a saldo, posizioni e ordini avvengono nella stessa
transazione: dopo un crash lo stato è sempre coerente (o l'operazione è
avvenuta per intero, o non è avvenuta affatto).
"""

from __future__ import annotations

from datetime import datetime, timezone

from atlas.domain import EXIT_REASON_IT, ExitReason, Fill, MarketRules, RiskDecision, ScoreResult, Signal
from atlas.execution.paper import OrderRejected, PaperBroker, make_client_order_id
from atlas.risk.manager import OpenPositionView, PortfolioState
from atlas.storage.db import Database


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class PaperAccount:
    def __init__(self, db: Database, broker: PaperBroker, initial_capital: float, clock=None) -> None:
        self.db = db
        self.broker = broker
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        if db.get_state("cash") is None:
            with db.transaction() as conn:
                db.set_state("initial_capital", initial_capital, conn)
                db.set_state("cash", initial_capital, conn)
                db.set_state("peak_equity", initial_capital, conn)
                db.set_state("day", self.clock().date().isoformat(), conn)
                db.set_state("day_start_equity", initial_capital, conn)
                db.set_state("consecutive_losses", 0, conn)
                db.set_state("paused", False, conn)
                db.set_state("halted", False, conn)
            db.log_event("account_created", f"Conto paper creato con {initial_capital:.2f}")

    # --- lettura ----------------------------------------------------------
    @property
    def cash(self) -> float:
        return float(self.db.get_state("cash", 0.0))

    @property
    def initial_capital(self) -> float:
        return float(self.db.get_state("initial_capital", 0.0))

    def equity(self, prices: dict[str, float] | None = None) -> float:
        prices = prices or {}
        value = sum(p["quantity"] * prices.get(p["symbol"], p["last_price"] if p.get("last_price") else p["entry_price"]) for p in self._open_with_last())
        return self.cash + value

    def _open_with_last(self) -> list[dict]:
        out = []
        last_prices = self.db.get_state("last_prices", {}) or {}
        for p in self.db.open_positions():
            p["last_price"] = last_prices.get(p["symbol"], p["entry_price"])
            out.append(p)
        return out

    def state(self, prices: dict[str, float] | None = None, now: datetime | None = None) -> PortfolioState:
        now = now or self.clock()
        prices = prices or {}
        positions = self._open_with_last()
        views = [
            OpenPositionView(
                symbol=p["symbol"],
                quantity=p["quantity"],
                entry_price=p["entry_price"],
                current_price=prices.get(p["symbol"], p["last_price"]),
                stop_loss=p["stop_loss"],
            )
            for p in positions
        ]
        equity = self.cash + sum(v.exposure for v in views)
        self._roll_day(equity, now)
        last_loss = self.db.get_state("last_loss_at")
        return PortfolioState(
            cash=self.cash,
            equity=equity,
            peak_equity=max(float(self.db.get_state("peak_equity", equity)), equity),
            day_start_equity=float(self.db.get_state("day_start_equity", equity)),
            positions=views,
            consecutive_losses=int(self.db.get_state("consecutive_losses", 0)),
            last_loss_at=datetime.fromisoformat(last_loss) if last_loss else None,
            paused=bool(self.db.get_state("paused", False)),
            halted=bool(self.db.get_state("halted", False)),
            halt_reason=self.db.get_state("halt_reason"),
        )

    def _roll_day(self, equity: float, now: datetime) -> None:
        today = now.date().isoformat()
        if self.db.get_state("day") != today:
            with self.db.transaction() as conn:
                self.db.set_state("day", today, conn)
                self.db.set_state("day_start_equity", equity, conn)

    def mark_to_market(self, prices: dict[str, float]) -> PortfolioState:
        last = self.db.get_state("last_prices", {}) or {}
        last.update(prices)
        self.db.set_state("last_prices", last)
        st = self.state(prices)
        if st.equity > float(self.db.get_state("peak_equity", 0.0)):
            self.db.set_state("peak_equity", st.equity)
        return st

    # --- controllo --------------------------------------------------------
    def set_paused(self, paused: bool) -> None:
        self.db.set_state("paused", paused)
        self.db.log_event("pause" if paused else "resume", "Nuove operazioni sospese" if paused else "Nuove operazioni riprese")

    def halt(self, reason: str) -> None:
        with self.db.transaction() as conn:
            self.db.set_state("halted", True, conn)
            self.db.set_state("halt_reason", reason, conn)
        self.db.log_event("halt", f"Arresto di sicurezza: {reason}", level="CRITICAL")

    def clear_halt(self, reset_peak: bool = False) -> None:
        with self.db.transaction() as conn:
            self.db.set_state("halted", False, conn)
            self.db.set_state("halt_reason", None, conn)
            if reset_peak:
                self.db.set_state("peak_equity", self.equity(), conn)
        self.db.log_event("halt_cleared", "Arresto di sicurezza rimosso manualmente", level="WARNING")

    # --- operazioni -------------------------------------------------------
    def open_position(
        self,
        signal: Signal,
        risk: RiskDecision,
        score: ScoreResult,
        rules: MarketRules,
        reference_price: float,
        spread_pct: float | None,
        market_context: dict,
        now: datetime | None = None,
    ) -> dict | None:
        """Apre una posizione simulata. Restituisce None se il segnale era già stato eseguito."""
        now = now or self.clock()
        coid = make_client_order_id("paper", signal.symbol, signal.strategy, signal.strategy_version, signal.bar_timestamp, "buy")
        if self.db.order_exists(coid):
            return None
        fill: Fill = self.broker.buy(signal.symbol, risk.quantity, reference_price, self.cash, rules, coid, spread_pct)
        # rischio effettivo ricalcolato sul prezzo di riempimento
        risk_amount = (fill.price - signal.stop_loss) * fill.quantity + fill.fee
        with self.db.transaction() as conn:
            cash = float(self.db.get_state("cash"))
            if fill.cost + fill.fee > cash + 1e-9:
                raise OrderRejected("saldo insufficiente al momento dell'esecuzione")
            cur = conn.execute(
                """INSERT INTO positions(symbol, mode, strategy, strategy_version, status, opened_at, signal_bar_ts,
                       entry_price, quantity, entry_fee, initial_stop, stop_loss, take_profit, risk_amount, highest_price,
                       last_bar_ts, score, score_category, reasons, market_context, meta, client_order_id)
                   VALUES (?, 'paper', ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    signal.symbol, signal.strategy, signal.strategy_version, _iso(now), signal.bar_timestamp,
                    fill.price, fill.quantity, fill.fee, signal.stop_loss, signal.stop_loss, signal.take_profit,
                    risk_amount, fill.price, signal.bar_timestamp, score.score, score.category,
                    _json({"entry": signal.reasons, "invalidation": signal.invalidation, "risk_notes": risk.reasons}),
                    _json(market_context), _json(signal.meta), coid,
                ),
            )
            position_id = cur.lastrowid
            conn.execute(
                """INSERT INTO orders(client_order_id, position_id, mode, symbol, side, quantity, reference_price, price, fee, cost, status, created_at)
                   VALUES (?, ?, 'paper', ?, 'buy', ?, ?, ?, ?, ?, 'filled', ?)""",
                (coid, position_id, signal.symbol, fill.quantity, reference_price, fill.price, fill.fee, fill.cost, _iso(now)),
            )
            self.db.set_state("cash", cash - fill.cost - fill.fee, conn)
        self.db.log_event("position_opened", f"Aperta posizione {signal.symbol}", data={"position_id": position_id, "price": fill.price, "qty": fill.quantity})
        return self.db.position(position_id)

    def close_position(self, position: dict, reference_price: float, reason: ExitReason, detail: str = "", spread_pct: float | None = None, now: datetime | None = None) -> dict | None:
        now = now or self.clock()
        coid = make_client_order_id("paper", position["id"], "sell")
        if self.db.order_exists(coid):
            return None
        fill = self.broker.sell(position["symbol"], position["quantity"], reference_price, coid, spread_pct)
        proceeds = fill.cost - fill.fee
        entry_total = position["entry_price"] * position["quantity"] + position["entry_fee"]
        pnl = proceeds - entry_total
        initial_risk = (position["entry_price"] - position["initial_stop"]) * position["quantity"] + position["entry_fee"]
        r_multiple = pnl / initial_risk if initial_risk > 0 else 0.0
        with self.db.transaction() as conn:
            row = conn.execute("SELECT status FROM positions WHERE id = ?", (position["id"],)).fetchone()
            if row is None or row["status"] != "open":
                return None
            conn.execute(
                """INSERT INTO orders(client_order_id, position_id, mode, symbol, side, quantity, reference_price, price, fee, cost, status, created_at)
                   VALUES (?, ?, 'paper', ?, 'sell', ?, ?, ?, ?, ?, 'filled', ?)""",
                (coid, position["id"], position["symbol"], fill.quantity, reference_price, fill.price, fill.fee, fill.cost, _iso(now)),
            )
            conn.execute(
                """UPDATE positions SET status='closed', closed_at=?, exit_price=?, exit_fee=?, exit_reason=?, exit_detail=?,
                       pnl=?, pnl_pct=?, r_multiple=? WHERE id = ?""",
                (_iso(now), fill.price, fill.fee, reason.value, detail or EXIT_REASON_IT[reason], pnl, pnl / entry_total * 100, r_multiple, position["id"]),
            )
            cash = float(self.db.get_state("cash"))
            self.db.set_state("cash", cash + proceeds, conn)
            if pnl < 0:
                self.db.set_state("consecutive_losses", int(self.db.get_state("consecutive_losses", 0)) + 1, conn)
                self.db.set_state("last_loss_at", _iso(now), conn)
            else:
                self.db.set_state("consecutive_losses", 0, conn)
        self.db.log_event("position_closed", f"Chiusa posizione {position['symbol']} ({reason.value})", data={"position_id": position["id"], "pnl": pnl})
        return self.db.position(position["id"])


def _json(value) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, default=str)
