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
        near_support: bool = False,
        near_resistance: bool = False,
        extended_candle: bool = False,
        last_candle_direction: str = "Neutrale",
        volume_status: str = "Normale",
        price_action_pattern: str = "Nessuno",
        price_action_signal: str = "Neutrale",
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

        support_resistance_adjustment = (
            self._calculate_support_resistance_adjustment(
                action=action,
                near_support=near_support,
                near_resistance=near_resistance,
            )
        )

        confidence += support_resistance_adjustment["value"]

        if support_resistance_adjustment["factor"]:
            factors.append(
                support_resistance_adjustment["factor"]
            )

        candle_context_adjustment = (
            self._calculate_candle_context_adjustment(
                action=action,
                extended_candle=extended_candle,
                last_candle_direction=last_candle_direction,
            )
        )

        confidence += candle_context_adjustment["value"]

        if candle_context_adjustment["factor"]:
            factors.append(
                candle_context_adjustment["factor"]
            )

        confidence = max(
            0,
            min(round(confidence), 100),
        )

        volume_adjustment = self._calculate_volume_adjustment(
            action=action,
            volume_status=volume_status,
        )

        confidence += volume_adjustment["value"]

        if volume_adjustment["factor"]:
            factors.append(
                volume_adjustment["factor"]
            )

        price_action_adjustment = (
            self._calculate_price_action_adjustment(
                action=action,
                price_action_pattern=price_action_pattern,
                price_action_signal=price_action_signal,
            )
        )

        confidence += price_action_adjustment["value"]

        if price_action_adjustment["factor"]:
            factors.append(
               price_action_adjustment["factor"]
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

    def _calculate_support_resistance_adjustment(
        self,
        action: str,
        near_support: bool,
        near_resistance: bool,
    ) -> dict:
        """
        Modifica la confidenza in base alla vicinanza
        a supporti e resistenze.
        """

        if action == "Attendere":
            return {
                "value": 0,
                "factor": "",
            }

        if action == "Possibile acquisto":
            if near_resistance:
                return {
                    "value": -20,
                    "factor": (
                        "Long troppo vicino a una resistenza"
                    ),
                }

            if near_support:
                return {
                    "value": 10,
                    "factor": (
                        "Supporto favorevole al Long"
                    ),
                }

        if action == "Possibile vendita":
            if near_support:
                return {
                    "value": -20,
                    "factor": (
                        "Short troppo vicino a un supporto"
                    ),
                }

            if near_resistance:
                return {
                    "value": 10,
                    "factor": (
                        "Resistenza favorevole allo Short"
                    ),
                }

        return {
            "value": 0,
            "factor": "",
        }

    def _calculate_candle_context_adjustment(
        self,
        action: str,
        extended_candle: bool,
        last_candle_direction: str,
    ) -> dict:
        """
        Penalizza gli ingressi tardivi dopo una candela
        estesa nella stessa direzione del trade.
        """

        if action == "Attendere":
            return {
                "value": 0,
                "factor": "",
            }

        if not extended_candle:
            return {
                "value": 0,
                "factor": "",
            }

        if (
            action == "Possibile acquisto"
            and last_candle_direction == "Rialzista"
        ):
            return {
                "value": -20,
                "factor": (
                    "Long dopo una candela rialzista troppo estesa"
                ),
            }

        if (
            action == "Possibile vendita"
            and last_candle_direction == "Ribassista"
        ):
            return {
                "value": -20,
                "factor": (
                    "Short dopo una candela ribassista troppo estesa"
                ),
            }

        return {
            "value": -5,
            "factor": (
                "Ultima candela estesa in direzione opposta"
            ),
        }

    def _calculate_volume_adjustment(
        self,
        action: str,
        volume_status: str,
    ) -> dict:
        """
        Modifica la confidence in base alla conferma fornita dal volume.
        """

        if action == "Attendere":
            return {
                "value": 0,
                "factor": "",
            }

        if volume_status == "Alto":
            return {
                "value": 10,
                "factor": "Volume alto a conferma del segnale",
            }

        if volume_status == "Basso":
            return {
                "value": -15,
                "factor": "Volume basso: segnale poco confermato",
            }

        return {
            "value": 0,
            "factor": "Volume nella norma",
        }

    def _calculate_price_action_adjustment(
        self,
        action: str,
        price_action_pattern: str,
        price_action_signal: str,
    ) -> dict:
        """
        Modifica la confidence in base alla coerenza
        della Price Action con la direzione operativa.
        """

        if action == "Attendere":
            return {
                "value": 0,
                "factor": "",
            }

        if price_action_pattern == "Nessuno":
            return {
                "value": 0,
                "factor": "",
            }

        if price_action_pattern == "Doji":
            return {
                "value": -5,
                "factor": "Doji: indecisione nella Price Action",
            }

        if action == "Possibile acquisto":
            if price_action_signal == "Rialzista":
                return {
                    "value": 10,
                    "factor": "Price Action favorevole al Long",
                }

            if price_action_signal == "Ribassista":
                return {
                    "value": -15,
                    "factor": "Price Action contraria al Long",
                }

        if action == "Possibile vendita":
            if price_action_signal == "Ribassista":
                return {
                    "value": 10,
                    "factor": "Price Action favorevole allo Short",
                }

            if price_action_signal == "Rialzista":
                return {
                    "value": -15,
                    "factor": "Price Action contraria allo Short",
                }

        return {
            "value": 0,
            "factor": "",
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