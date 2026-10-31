"""Risk manager: l'unico componente che può approvare una nuova posizione.

Un segnale viene rifiutato se viola anche una sola regola, indipendentemente
dal punteggio. Il risk manager è puro (nessun I/O): riceve lo stato del
portafoglio e restituisce una decisione motivata. È condiviso tra paper
trading e backtest, così le regole simulate e quelle testate coincidono.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from atlas.domain import MarketRules, RiskDecision, Signal
from atlas.risk.costs import CostModel, net_reward_risk


@dataclass(frozen=True)
class RiskLimits:
    risk_per_trade_pct: float = 1.0
    max_position_pct: float = 50.0
    max_exposure_pct: float = 80.0
    max_open_positions: int = 2
    max_daily_loss_pct: float = 3.0
    max_drawdown_pct: float = 15.0
    max_consecutive_losses: int = 4
    cooldown_hours_after_losses: int = 24
    max_correlated_risk_pct: float = 1.5
    correlation_threshold: float = 0.8
    min_reward_risk: float = 1.8
    max_spread_pct: float = 0.5
    min_order_cost: float = 5.0
    max_cost_to_risk: float = 0.6   # costi andata/ritorno al massimo il 60% del rischio

    @classmethod
    def from_settings(cls, s) -> "RiskLimits":
        return cls(
            risk_per_trade_pct=s.risk_per_trade_pct,
            max_position_pct=s.max_position_pct,
            max_exposure_pct=s.max_exposure_pct,
            max_open_positions=s.max_open_positions,
            max_daily_loss_pct=s.max_daily_loss_pct,
            max_drawdown_pct=s.max_drawdown_pct,
            max_consecutive_losses=s.max_consecutive_losses,
            cooldown_hours_after_losses=s.cooldown_hours_after_losses,
            max_correlated_risk_pct=s.max_correlated_risk_pct,
            correlation_threshold=s.correlation_threshold,
            min_reward_risk=s.min_reward_risk,
            max_spread_pct=s.max_spread_pct,
            min_order_cost=s.min_order_cost,
        )


@dataclass
class OpenPositionView:
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    stop_loss: float

    @property
    def exposure(self) -> float:
        return self.quantity * self.current_price

    @property
    def open_risk(self) -> float:
        """Perdita residua se lo stop venisse colpito (0 se lo stop è in profitto)."""
        return max(0.0, (self.current_price - self.stop_loss) * self.quantity)


@dataclass
class PortfolioState:
    cash: float
    equity: float
    peak_equity: float
    day_start_equity: float
    positions: list[OpenPositionView] = field(default_factory=list)
    consecutive_losses: int = 0
    last_loss_at: datetime | None = None
    paused: bool = False
    halted: bool = False
    halt_reason: str | None = None

    @property
    def exposure(self) -> float:
        return sum(p.exposure for p in self.positions)

    @property
    def drawdown_pct(self) -> float:
        return (self.peak_equity - self.equity) / self.peak_equity * 100 if self.peak_equity > 0 else 0.0

    @property
    def daily_pnl_pct(self) -> float:
        return (self.equity - self.day_start_equity) / self.day_start_equity * 100 if self.day_start_equity > 0 else 0.0


class RiskManager:
    def __init__(self, limits: RiskLimits, costs: CostModel) -> None:
        self.limits = limits
        self.costs = costs

    # --- controlli di portafoglio (prima di qualunque segnale) ---------
    def portfolio_blocks(self, state: PortfolioState, now: datetime) -> list[str]:
        L = self.limits
        blocks: list[str] = []
        if state.halted:
            blocks.append(f"sistema in arresto di sicurezza: {state.halt_reason or 'motivo non specificato'}")
        if state.paused:
            blocks.append("nuove operazioni in pausa (comando /pausa)")
        if state.daily_pnl_pct <= -L.max_daily_loss_pct:
            blocks.append(f"limite di perdita giornaliera raggiunto ({state.daily_pnl_pct:.2f}% ≤ -{L.max_daily_loss_pct}%)")
        if state.drawdown_pct >= L.max_drawdown_pct:
            blocks.append(f"drawdown massimo raggiunto ({state.drawdown_pct:.2f}% ≥ {L.max_drawdown_pct}%)")
        if (
            state.consecutive_losses >= L.max_consecutive_losses
            and state.last_loss_at is not None
            and now - state.last_loss_at < timedelta(hours=L.cooldown_hours_after_losses)
        ):
            blocks.append(
                f"{state.consecutive_losses} perdite consecutive: pausa di {L.cooldown_hours_after_losses}h dall'ultima perdita"
            )
        if len(state.positions) >= L.max_open_positions:
            blocks.append(f"numero massimo di posizioni aperte raggiunto ({L.max_open_positions})")
        return blocks

    def should_halt(self, state: PortfolioState) -> str | None:
        """Condizioni che richiedono l'arresto (sblocco solo manuale)."""
        if state.drawdown_pct >= self.limits.max_drawdown_pct:
            return f"drawdown {state.drawdown_pct:.2f}% oltre il limite del {self.limits.max_drawdown_pct}%"
        return None

    # --- valutazione del singolo segnale --------------------------------
    def evaluate(
        self,
        signal: Signal,
        state: PortfolioState,
        rules: MarketRules,
        now: datetime,
        spread_pct: float | None = None,
        correlations: dict[str, float] | None = None,
    ) -> RiskDecision:
        L = self.limits
        reasons: list[str] = []
        checks: dict[str, bool] = {}
        costs = self.costs.with_spread(spread_pct)

        blocks = self.portfolio_blocks(state, now)
        checks["portafoglio"] = not blocks
        reasons.extend(blocks)

        dup = any(p.symbol == signal.symbol for p in state.positions)
        checks["nessun_duplicato"] = not dup
        if dup:
            reasons.append(f"posizione già aperta su {signal.symbol}")

        spread_ok = spread_pct is None or spread_pct <= L.max_spread_pct
        checks["spread"] = spread_ok
        if not spread_ok:
            reasons.append(f"spread troppo ampio ({spread_pct:.2f}% > {L.max_spread_pct}%)")

        valid_levels = signal.stop_loss < signal.entry_price < signal.take_profit and signal.stop_loss > 0
        checks["livelli_validi"] = valid_levels
        if not valid_levels:
            reasons.append("livelli di stop/target non validi")
            return RiskDecision(False, reasons=reasons, checks=checks)

        rr, risk_unit, _ = net_reward_risk(signal.entry_price, signal.stop_loss, signal.take_profit, costs)
        checks["reward_risk"] = rr >= L.min_reward_risk
        if rr < L.min_reward_risk:
            reasons.append(f"rapporto rendimento/rischio netto {rr:.2f} inferiore al minimo {L.min_reward_risk}")

        buy_price = costs.entry_price(signal.entry_price)
        cost_share = (2 * costs.per_side_pct / 100 * buy_price) / risk_unit if risk_unit > 0 else 1.0
        checks["costi"] = cost_share <= L.max_cost_to_risk
        if cost_share > L.max_cost_to_risk:
            reasons.append(f"i costi di esecuzione valgono il {cost_share:.0%} del rischio: stop troppo vicino per questo capitale")

        equity = state.equity
        risk_budget = equity * L.risk_per_trade_pct / 100
        qty = risk_budget / risk_unit if risk_unit > 0 else 0.0
        notes: list[str] = []

        caps = {
            "dimensione massima per posizione": equity * L.max_position_pct / 100,
            "esposizione totale massima": equity * L.max_exposure_pct / 100 - state.exposure,
            "liquidità disponibile": state.cash / (1 + costs.fee_pct / 100),
        }
        for label, cap_cost in caps.items():
            max_qty = max(cap_cost, 0.0) / buy_price
            if qty > max_qty:
                qty = max_qty
                notes.append(f"quantità ridotta per {label}")

        if correlations:
            correlated_risk = sum(
                p.open_risk for p in state.positions if correlations.get(p.symbol, 0.0) >= L.correlation_threshold
            )
            corr_cap = equity * L.max_correlated_risk_pct / 100 - correlated_risk
            if corr_cap <= 0:
                reasons.append("rischio su asset correlati già al limite")
                checks["correlazione"] = False
                qty = 0.0
            else:
                checks["correlazione"] = True
                max_qty = corr_cap / risk_unit
                if qty > max_qty:
                    qty = max_qty
                    notes.append("quantità ridotta per correlazione con posizioni aperte")

        qty = rules.round_amount(qty)
        cost = qty * buy_price
        min_cost = max(rules.min_cost, L.min_order_cost)
        size_ok = qty > 0 and qty >= rules.min_amount and cost >= min_cost
        checks["minimi_ordine"] = size_ok
        if not size_ok:
            reasons.append(
                f"ordine sotto i minimi dell'exchange o di sicurezza (controvalore {cost:.2f} < {min_cost:.2f} {signal.symbol.split('/')[-1]})"
            )

        approved = all(checks.values())
        risk_amount = qty * risk_unit
        fees = costs.fee(cost) + costs.fee(qty * signal.take_profit)
        return RiskDecision(
            approved=approved,
            quantity=qty if approved else 0.0,
            cost=round(cost, 8) if approved else 0.0,
            risk_amount=round(risk_amount, 8),
            risk_pct=round(risk_amount / equity * 100, 3) if equity > 0 else 0.0,
            net_reward_risk=round(rr, 3),
            estimated_fees=round(fees, 8),
            reasons=reasons if not approved else notes,
            checks=checks,
        )
