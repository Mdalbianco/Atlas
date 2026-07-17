class ScoreCalculator:
    """Calcola lo score complessivo dell'analisi."""

    def calculate(
        self,
        trend: str,
        trend_strength: int,
        rsi: float,
    ) -> int:
        score = 50

        if trend == "Rialzista":
            score += round(trend_strength * 0.3)

        elif trend == "Ribassista":
            score -= round(trend_strength * 0.3)

        if rsi <= 30:
            score += 15

        elif rsi >= 70:
            score -= 15

        return max(0, min(score, 100))