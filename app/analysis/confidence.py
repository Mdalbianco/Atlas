class ConfidenceCalculator:
    """Calcola quanto Atlas può fidarsi della propria valutazione."""

    def calculate(
        self,
        score: int,
        action: str,
        trend: str,
        macd_status: str,
        rsi: float,
        atr_percentage: float,
    ) -> dict:
        confidence = float(score)
        factors = []

        if action == "Possibile acquisto":
            if trend == "Rialzista":
                confidence += 5
                factors.append("Trend coerente con il Long")
            else:
                confidence -= 10
                factors.append("Trend non coerente con il Long")

            if macd_status == "Positivo":
                confidence += 5
                factors.append("MACD favorevole al Long")
            elif macd_status == "Negativo":
                confidence -= 10
                factors.append("MACD contrario al Long")

            if rsi >= 70:
                confidence -= 10
                factors.append("RSI troppo alto per un Long")

        elif action == "Possibile vendita":
            if trend == "Ribassista":
                confidence += 5
                factors.append("Trend coerente con lo Short")
            else:
                confidence -= 10
                factors.append("Trend non coerente con lo Short")

            if macd_status == "Negativo":
                confidence += 5
                factors.append("MACD favorevole allo Short")
            elif macd_status == "Positivo":
                confidence -= 10
                factors.append("MACD contrario allo Short")

            if rsi <= 30:
                confidence -= 10
                factors.append("RSI troppo basso per uno Short")

        else:
            confidence = min(confidence, 35)
            factors.append("Nessuna direzione operativa confermata")

        if atr_percentage < 0.10:
            confidence -= 5
            factors.append("Volatilità troppo bassa")

        elif atr_percentage <= 4.00:
            confidence += 5
            factors.append("Volatilità operativa adeguata")

        elif atr_percentage > 6.00:
            confidence -= 10
            factors.append("Volatilità eccessiva")

        confidence = max(
            0,
            min(round(confidence), 100),
        )

        return {
            "confidence": confidence,
            "confidence_classification": self.classify(confidence),
            "confidence_factors": factors,
        }

    def classify(self, confidence: int) -> str:
        """Classifica il livello di confidenza."""

        if confidence >= 85:
            return "Molto alta"

        if confidence >= 70:
            return "Alta"

        if confidence >= 55:
            return "Media"

        if confidence >= 40:
            return "Bassa"

        return "Molto bassa"