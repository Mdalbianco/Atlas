import pandas as pd


class SupportResistanceAnalyzer:
    """
    Individua supporto e resistenza vicini usando
    i massimi e i minimi locali delle candele.
    """

    def analyze(
        self,
        dataframe: pd.DataFrame,
        current_price: float,
        window: int = 5,
        tolerance_percentage: float = 0.35,
    ) -> dict:
        self._validate_inputs(
            dataframe=dataframe,
            current_price=current_price,
            window=window,
        )

        support_levels = self._find_support_levels(
            dataframe=dataframe,
            window=window,
        )

        resistance_levels = self._find_resistance_levels(
            dataframe=dataframe,
            window=window,
        )

        nearest_support = self._find_nearest_support(
            levels=support_levels,
            current_price=current_price,
        )

        nearest_resistance = self._find_nearest_resistance(
            levels=resistance_levels,
            current_price=current_price,
        )

        support_distance_percentage = self._calculate_distance_percentage(
            current_price=current_price,
            level=nearest_support,
        )

        resistance_distance_percentage = self._calculate_distance_percentage(
            current_price=current_price,
            level=nearest_resistance,
        )

        near_support = (
            support_distance_percentage is not None
            and support_distance_percentage <= tolerance_percentage
        )

        near_resistance = (
            resistance_distance_percentage is not None
            and resistance_distance_percentage <= tolerance_percentage
        )

        factors = []

        if near_support:
            factors.append("Prezzo vicino a un supporto")

        if near_resistance:
            factors.append("Prezzo vicino a una resistenza")

        if not factors:
            factors.append(
                "Prezzo sufficientemente distante dai livelli principali"
            )

        return {
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,
            "support_distance_percentage": support_distance_percentage,
            "resistance_distance_percentage": resistance_distance_percentage,
            "near_support": near_support,
            "near_resistance": near_resistance,
            "support_resistance_factors": factors,
        }

    def _find_support_levels(
        self,
        dataframe: pd.DataFrame,
        window: int,
    ) -> list[float]:
        lows = dataframe["low"].astype(float)

        rolling_minimum = lows.rolling(
            window=(window * 2) + 1,
            center=True,
        ).min()

        levels = lows[lows == rolling_minimum].dropna().tolist()

        return self._remove_similar_levels(levels)

    def _find_resistance_levels(
        self,
        dataframe: pd.DataFrame,
        window: int,
    ) -> list[float]:
        highs = dataframe["high"].astype(float)

        rolling_maximum = highs.rolling(
            window=(window * 2) + 1,
            center=True,
        ).max()

        levels = highs[highs == rolling_maximum].dropna().tolist()

        return self._remove_similar_levels(levels)

    def _find_nearest_support(
        self,
        levels: list[float],
        current_price: float,
    ) -> float | None:
        valid_levels = [
            level
            for level in levels
            if level <= current_price
        ]

        if not valid_levels:
            return None

        return round(max(valid_levels), 8)

    def _find_nearest_resistance(
        self,
        levels: list[float],
        current_price: float,
    ) -> float | None:
        valid_levels = [
            level
            for level in levels
            if level >= current_price
        ]

        if not valid_levels:
            return None

        return round(min(valid_levels), 8)

    def _calculate_distance_percentage(
        self,
        current_price: float,
        level: float | None,
    ) -> float | None:
        if level is None:
            return None

        distance = abs(current_price - level)

        percentage = (
            distance / current_price
        ) * 100

        return round(percentage, 2)

    def _remove_similar_levels(
        self,
        levels: list[float],
        minimum_distance_percentage: float = 0.20,
    ) -> list[float]:
        if not levels:
            return []

        ordered_levels = sorted(
            float(level)
            for level in levels
        )

        filtered_levels = [ordered_levels[0]]

        for level in ordered_levels[1:]:
            previous_level = filtered_levels[-1]

            distance_percentage = (
                abs(level - previous_level)
                / previous_level
            ) * 100

            if distance_percentage >= minimum_distance_percentage:
                filtered_levels.append(level)

        return filtered_levels

    def _validate_inputs(
        self,
        dataframe: pd.DataFrame,
        current_price: float,
        window: int,
    ) -> None:
        required_columns = {
            "high",
            "low",
        }

        missing_columns = (
            required_columns
            - set(dataframe.columns)
        )

        if missing_columns:
            raise ValueError(
                "Colonne mancanti nel dataframe: "
                f"{sorted(missing_columns)}"
            )

        if dataframe.empty:
            raise ValueError(
                "Il dataframe non può essere vuoto."
            )

        if current_price <= 0:
            raise ValueError(
                "Il prezzo corrente deve essere maggiore di zero."
            )

        if window < 1:
            raise ValueError(
                "La finestra deve essere almeno 1."
            )