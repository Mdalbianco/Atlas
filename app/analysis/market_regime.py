class MarketRegimeDetector:
    """Classifica il contesto generale del mercato."""

    def detect(
        self,
        trend: str,
        trend_strength: int,
        atr_percentage: float,
        rsi: float,
        macd_status: str,
    ) -> dict:
        normalized_strength = max(
            0,
            min(int(trend_strength), 100),
        )

        regime = "Laterale"
        regime_score = 50
        factors = []

        if atr_percentage < 0.15:
            regime = "Mercato piatto"
            regime_score = 25
            factors.append("Volatilità molto bassa")

        elif atr_percentage > 4.0:
            regime = "Alta volatilità"
            regime_score = 35
            factors.append("Volatilità elevata")

        elif (
            trend == "Rialzista"
            and normalized_strength >= 60
            and macd_status == "Positivo"
        ):
            regime = "Trend rialzista forte"
            regime_score = 85
            factors.append("Trend rialzista forte")
            factors.append("MACD coerente")

        elif (
            trend == "Ribassista"
            and normalized_strength >= 60
            and macd_status == "Negativo"
        ):
            regime = "Trend ribassista forte"
            regime_score = 85
            factors.append("Trend ribassista forte")
            factors.append("MACD coerente")

        elif trend == "Rialzista":
            regime = "Trend rialzista debole"
            regime_score = 65
            factors.append("Trend rialzista presente")

        elif trend == "Ribassista":
            regime = "Trend ribassista debole"
            regime_score = 65
            factors.append("Trend ribassista presente")

        if 40 <= rsi <= 60:
            factors.append("RSI in area neutrale")

        elif rsi >= 70:
            factors.append("RSI in ipercomprato")

        elif rsi <= 30:
            factors.append("RSI in ipervenduto")

        if not factors:
            factors.append("Nessun segnale dominante")

        return {
            "market_regime": regime,
            "market_regime_score": regime_score,
            "market_regime_factors": factors,
        }