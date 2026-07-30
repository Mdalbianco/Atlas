class ScoreCalculator:
    """Calcola la qualità complessiva di un setup da 0 a 100."""

    def calculate(
        self,
        trend: str,
        trend_strength: int,
        rsi: float,
        action: str = "Attendere",
        macd_status: str = "Neutrale",
        atr_percentage: float = 0.0,
    ) -> int:
        score = 50

        normalized_strength = max(
            0,
            min(int(trend_strength), 100),
        )

        trend_points = round(
            normalized_strength * 0.30
        )

        if action == "Possibile acquisto":
            score += self._calculate_long_score(
                trend=trend,
                trend_points=trend_points,
                rsi=rsi,
                macd_status=macd_status,
            )

        elif action == "Possibile vendita":
            score += self._calculate_short_score(
                trend=trend,
                trend_points=trend_points,
                rsi=rsi,
                macd_status=macd_status,
            )

        else:
            score += self._calculate_neutral_score(
                trend=trend,
                rsi=rsi,
                macd_status=macd_status,
            )

        score += self._calculate_volatility_score(
            atr_percentage
        )

        score = max(
            0,
            min(round(score), 100),
        )

        if action == "Attendere":
            score = min(score, 49)

        return score

    def classify(self, score: int) -> str:
        """Restituisce la classificazione qualitativa dello score."""

        if score >= 85:
            return "Eccellente"

        if score >= 75:
            return "Molto buono"

        if score >= 65:
            return "Buono"

        if score >= 50:
            return "Debole"

        return "Insufficiente"

    def is_acceptable(
        self,
        score: int,
        minimum_score: int = 65,
    ) -> bool:
        """Controlla se lo score supera la soglia minima."""

        return score >= minimum_score

    def _calculate_long_score(
        self,
        trend: str,
        trend_points: int,
        rsi: float,
        macd_status: str,
    ) -> int:
        score = 0

        if trend == "Rialzista":
            score += trend_points

        elif trend == "Ribassista":
            score -= trend_points

        if rsi <= 30:
            score += 15

        elif rsi < 60:
            score += 5

        elif rsi >= 70:
            score -= 15

        if macd_status == "Positivo":
            score += 15

        elif macd_status == "Negativo":
            score -= 15

        return score

    def _calculate_short_score(
        self,
        trend: str,
        trend_points: int,
        rsi: float,
        macd_status: str,
    ) -> int:
        score = 0

        if trend == "Ribassista":
            score += trend_points

        elif trend == "Rialzista":
            score -= trend_points

        if rsi >= 70:
            score += 15

        elif rsi > 40:
            score += 5

        elif rsi <= 30:
            score -= 15

        if macd_status == "Negativo":
            score += 15

        elif macd_status == "Positivo":
            score -= 15

        return score

    def _calculate_neutral_score(
        self,
        trend: str,
        rsi: float,
        macd_status: str,
    ) -> int:
        score = -15

        if trend not in {
            "Rialzista",
            "Ribassista",
        }:
            score += 5

        if 40 <= rsi <= 60:
            score += 5

        if macd_status not in {
            "Positivo",
            "Negativo",
        }:
            score += 5

        return score

    def _calculate_volatility_score(
        self,
        atr_percentage: float,
    ) -> int:
        """
        Premia una volatilità sufficiente per operare,
        ma penalizza mercati troppo fermi o estremi.
        """

        if atr_percentage <= 0:
            return 0

        if atr_percentage < 0.10:
            return -5

        if atr_percentage <= 2.50:
            return 10

        if atr_percentage <= 4.00:
            return 5

        if atr_percentage > 6.00:
            return -10

        return 0