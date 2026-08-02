class MultiTimeframeAnalyzer:
    """Valuta l'allineamento tra il timeframe operativo e quello principale."""

    def analyze(
        self,
        lower_trend: str,
        lower_strength: int,
        higher_trend: str,
        higher_strength: int,
        action: str,
    ) -> dict:
        lower_strength = self._normalize_strength(lower_strength)
        higher_strength = self._normalize_strength(higher_strength)

        alignment_score = 50
        factors = []

        same_direction = lower_trend == higher_trend

        if same_direction:
            alignment_score += 25
            factors.append("Trend 1H e 4H nella stessa direzione")
        else:
            alignment_score -= 25
            factors.append("Trend 1H e 4H in direzioni opposte")

        average_strength = round(
            (lower_strength + higher_strength) / 2
        )

        if average_strength >= 70:
            alignment_score += 15
            factors.append("Forza media dei trend elevata")

        elif average_strength >= 40:
            alignment_score += 5
            factors.append("Forza media dei trend sufficiente")

        else:
            alignment_score -= 10
            factors.append("Forza media dei trend debole")

        action_alignment = self._calculate_action_alignment(
            action=action,
            lower_trend=lower_trend,
            higher_trend=higher_trend,
        )

        alignment_score += action_alignment["value"]

        if action_alignment["factor"]:
            factors.append(action_alignment["factor"])

        alignment_score = max(
            0,
            min(round(alignment_score), 100),
        )

        aligned = (
            alignment_score >= 65
            and action_alignment["compatible"]
        )

        return {
            "lower_timeframe": "1h",
            "higher_timeframe": "4h",
            "lower_timeframe_trend": lower_trend,
            "lower_timeframe_strength": lower_strength,
            "higher_timeframe_trend": higher_trend,
            "higher_timeframe_strength": higher_strength,
            "timeframe_alignment_score": alignment_score,
            "timeframe_alignment": self.classify(alignment_score),
            "timeframe_aligned": aligned,
            "timeframe_factors": factors,
        }

    def _calculate_action_alignment(
        self,
        action: str,
        lower_trend: str,
        higher_trend: str,
    ) -> dict:
        """Controlla se la decisione è coerente con entrambi i timeframe."""

        if action == "Attendere":
            return {
                "value": 0,
                "compatible": False,
                "factor": "Nessuna direzione operativa confermata",
            }

        if action == "Possibile acquisto":
            if (
                lower_trend == "Rialzista"
                and higher_trend == "Rialzista"
            ):
                return {
                    "value": 10,
                    "compatible": True,
                    "factor": "Long coerente con entrambi i timeframe",
                }

            if higher_trend == "Ribassista":
                return {
                    "value": -20,
                    "compatible": False,
                    "factor": "Long contrario al trend principale 4H",
                }

        if action == "Possibile vendita":
            if (
                lower_trend == "Ribassista"
                and higher_trend == "Ribassista"
            ):
                return {
                    "value": 10,
                    "compatible": True,
                    "factor": "Short coerente con entrambi i timeframe",
                }

            if higher_trend == "Rialzista":
                return {
                    "value": -20,
                    "compatible": False,
                    "factor": "Short contrario al trend principale 4H",
                }

        return {
            "value": -10,
            "compatible": False,
            "factor": "Decisione non pienamente coerente con i timeframe",
        }

    def _normalize_strength(self, strength: int) -> int:
        return max(
            0,
            min(int(strength), 100),
        )

    def classify(self, alignment_score: int) -> str:
        if alignment_score >= 85:
            return "Molto forte"

        if alignment_score >= 70:
            return "Forte"

        if alignment_score >= 55:
            return "Parziale"

        if alignment_score >= 40:
            return "Debole"

        return "Contrario"