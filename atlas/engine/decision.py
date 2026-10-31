"""Motore decisionale: dai dati alla decisione motivata.

Sequenza (si ferma al primo blocco, ma registra sempre il perché):
1. controlli di sicurezza sui dati (anomalie, spread);
2. valutazione di tutte le strategie attive → segnali candidati;
3. scoring di ogni segnale; scarto sotto la soglia minima;
4. scelta del segnale con punteggio più alto;
5. verifica del risk manager (può rifiutare qualunque segnale).

Il default è NON operare: serve che tutte le condizioni siano soddisfatte.
"""

from __future__ import annotations

from datetime import datetime

from atlas.analysis.snapshot import MarketContext
from atlas.domain import Action, Decision, MarketRules
from atlas.risk.manager import PortfolioState, RiskManager
from atlas.scoring import ScoreEngine
from atlas.strategy.base import Strategy


class DecisionEngine:
    def __init__(self, strategies: list[Strategy], scorer: ScoreEngine, risk: RiskManager, min_score: float) -> None:
        self.strategies = strategies
        self.scorer = scorer
        self.risk = risk
        self.min_score = min_score

    def decide_entry(
        self,
        ctx: MarketContext,
        state: PortfolioState,
        rules: MarketRules,
        now: datetime,
        correlations: dict[str, float] | None = None,
    ) -> Decision:
        p = ctx.primary
        if p.anomaly:
            return Decision(ctx.symbol, Action.SKIP, "Condizioni anomale: nessuna operazione", [p.anomaly_reason or "anomalia"], bar_timestamp=p.timestamp)

        candidates = []
        rejected: list[str] = []
        for strat in self.strategies:
            if p.regime not in strat.regimes:
                rejected.append(f"{strat.name}: regime '{p.regime}' non compatibile (opera in: {', '.join(strat.regimes)})")
                continue
            ev = strat.evaluate(ctx)
            if ev.signal is None:
                rejected.append(f"{strat.name}: " + "; ".join(ev.reasons[:3]))
                continue
            sc = self.scorer.score(ev.signal, ctx)
            if sc.score < self.min_score:
                rejected.append(f"{strat.name}: punteggio {sc.score:.0f} sotto la soglia {self.min_score:.0f} ({sc.category})")
                candidates.append((sc, ev.signal, False))
                continue
            candidates.append((sc, ev.signal, True))

        eligible = [c for c in candidates if c[2]]
        if not eligible:
            best = max(candidates, key=lambda c: c[0].score) if candidates else None
            return Decision(
                ctx.symbol,
                Action.SKIP,
                "Nessun setup valido: ATLAS attende condizioni migliori",
                rejected,
                signal=best[1] if best else None,
                score=best[0] if best else None,
                strategy=best[1].strategy if best else None,
                bar_timestamp=p.timestamp,
            )

        score, signal, _ = max(eligible, key=lambda c: c[0].score)
        risk = self.risk.evaluate(signal, state, rules, now, spread_pct=ctx.spread_pct, correlations=correlations)
        if not risk.approved:
            return Decision(
                ctx.symbol,
                Action.SKIP,
                f"Setup {signal.strategy} ({score.score:.0f}/100) rifiutato dal risk manager",
                risk.reasons,
                signal=signal,
                score=score,
                risk=risk,
                strategy=signal.strategy,
                bar_timestamp=p.timestamp,
            )
        return Decision(
            ctx.symbol,
            Action.ENTER,
            f"Operazione simulata approvata: {signal.strategy} ({score.score:.0f}/100)",
            signal.reasons + risk.reasons,
            signal=signal,
            score=score,
            risk=risk,
            strategy=signal.strategy,
            bar_timestamp=p.timestamp,
        )
