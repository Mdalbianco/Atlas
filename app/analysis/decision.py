class DecisionEngine:
    """Interpreta gli indicatori e genera una valutazione."""

    def analyze(
        self,
        trend: str,
        rsi: float,
        macd_status: str,
    ) -> dict:

        reasons = []

        score = 0

        if trend == "Rialzista":
            score += 2
            reasons.append("Trend rialzista")

        elif trend == "Ribassista":
            score -= 2
            reasons.append("Trend ribassista")

        if rsi <= 30:
            score += 1
            reasons.append("RSI in ipervenduto")

        elif rsi >= 70:
            score -= 1
            reasons.append("RSI in ipercomprato")

        if macd_status == "Positivo":
            score += 1
            reasons.append("MACD positivo")

        elif macd_status == "Negativo":
            score -= 1
            reasons.append("MACD negativo")

        if score >= 3:
            action = "Possibile acquisto"

        elif score <= -3:
            action = "Possibile vendita"

        else:
            action = "Attendere"

        return {
            "decision_score": score,
            "action": action,
            "reasons": reasons,
        }