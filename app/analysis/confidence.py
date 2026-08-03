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
        market_regime: str = "Non classificato",
        timeframe_alignment_score: int = 0,
        timeframe_aligned: bool = False,
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

        regime_adjustment = self._calculate_market_regime_adjustment(
            action=action,
            market_regime=market_regime,
        )

        confidence += regime_adjustment["value"]

        if regime_adjustment["factor"]:
            factors.append(regime_adjustment["factor"])

        timeframe_adjustment = self._calculate_timeframe_adjustment(
            action=action,
            timeframe_alignment_score=timeframe_alignment_score,
            timeframe_aligned=timeframe_aligned,
        )

        confidence += timeframe_adjustment["value"]

        if timeframe_adjustment["factor"]:
            factors.append(timeframe_adjustment["factor"])

        confidence = max(
            0,
            min(round(confidence), 100),
        )

        return {
            "confidence": confidence,
            "confidence_classification": self.classify(confidence),
            "confidence_factors": factors,
        }

    def _calculate_market_regime_adjustment(
        self,
        action: str,
        market_regime: str,
    ) -> dict:
        """Modifica la confidenza in base al regime di mercato."""

        if action == "Attendere":
            if market_regime == "Mercato piatto":
                return {
                    "value": -5,
                    "factor": "Mercato piatto senza opportunità operative",
                }

            if market_regime == "Alta volatilità":
                return {
                    "value": -5,
                    "factor": "Regime instabile senza direzione confermata",
                }

            return {
                "value": 0,
                "factor": "",
            }

        if market_regime == "Mercato piatto":
            return {
                "value": -15,
                "factor": "Regime piatto sfavorevole al setup",
            }

        if market_regime == "Alta volatilità":
            return {
                "value": -10,
                "factor": "Alta volatilità riduce l'affidabilità",
            }

        if action == "Possibile acquisto":
            if market_regime == "Trend rialzista forte":
                return {
                    "value": 10,
                    "factor": "Regime fortemente favorevole al Long",
                }

            if market_regime == "Trend rialzista debole":
                return {
                    "value": 5,
                    "factor": "Regime favorevole al Long",
                }

            if market_regime == "Trend ribassista forte":
                return {
                    "value": -15,
                    "factor": "Regime fortemente contrario al Long",
                }

            if market_regime == "Trend ribassista debole":
                return {
                    "value": -5,
                    "factor": "Regime contrario al Long",
                }

        if action == "Possibile vendita":
            if market_regime == "Trend ribassista forte":
                return {
                    "value": 10,
                    "factor": "Regime fortemente favorevole allo Short",
                }

            if market_regime == "Trend ribassista debole":
                return {
                    "value": 5,
                    "factor": "Regime favorevole allo Short",
                }

            if market_regime == "Trend rialzista forte":
                return {
                    "value": -15,
                    "factor": "Regime fortemente contrario allo Short",
                }

            if market_regime == "Trend rialzista debole":
                return {
                    "value": -5,
                    "factor": "Regime contrario allo Short",
                }

        return {
            "value": 0,
            "factor": "",
        }

    def _calculate_timeframe_adjustment(
        self,
        action: str,
        timeframe_alignment_score: int,
        timeframe_aligned: bool,
    ) -> dict:
        """Modifica la confidenza in base all'allineamento 1H/4H."""

        if action == "Attendere":
            return {
                "value": 0,
                "factor": "",
            }

        normalized_score = max(
            0,
            min(int(timeframe_alignment_score), 100),
        )

        if timeframe_aligned:
            if normalized_score >= 85:
                return {
                    "value": 15,
                    "factor": "Allineamento multi-timeframe molto forte",
                }

            if normalized_score >= 70:
                return {
                    "value": 10,
                    "factor": "Allineamento multi-timeframe favorevole",
                }

            if normalized_score >= 65:
                return {
                    "value": 5,
                    "factor": "Allineamento multi-timeframe sufficiente",
                }

        if normalized_score < 40:
            return {
                "value": -20,
                "factor": "Timeframe fortemente contrari",
            }

        if normalized_score < 55:
            return {
                "value": -15,
                "factor": "Timeframe contrari",
            }

        return {
            "value": -10,
            "factor": "Timeframe non pienamente coerenti",
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