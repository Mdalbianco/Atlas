import pandas as pd


class VolumeAnalyzer:
    """
    Analizza il volume dell'ultima candela confrontandolo
    con il volume medio recente.
    """

    def analyze(
        self,
        dataframe: pd.DataFrame,
        lookback: int = 20,
        high_volume_threshold: float = 1.5,
        low_volume_threshold: float = 0.7,
    ) -> dict:
        self._validate_inputs(
            dataframe=dataframe,
            lookback=lookback,
            high_volume_threshold=high_volume_threshold,
            low_volume_threshold=low_volume_threshold,
        )

        volumes = dataframe["volume"].astype(float)

        last_volume = float(volumes.iloc[-1])

        previous_volumes = volumes.iloc[-(lookback + 1):-1]

        if previous_volumes.empty:
            previous_volumes = volumes.iloc[:-1]

        average_volume = float(previous_volumes.mean())

        if average_volume <= 0:
            volume_ratio = 0.0
        else:
            volume_ratio = last_volume / average_volume

        if volume_ratio >= high_volume_threshold:
            volume_status = "Alto"
            volume_signal = "Conferma forte"
        elif volume_ratio <= low_volume_threshold:
            volume_status = "Basso"
            volume_signal = "Conferma debole"
        else:
            volume_status = "Normale"
            volume_signal = "Conferma neutrale"

        factors = []

        if volume_status == "Alto":
            factors.append(
                "Volume superiore alla media recente"
            )
        elif volume_status == "Basso":
            factors.append(
                "Volume inferiore alla media recente"
            )
        else:
            factors.append(
                "Volume nella media recente"
            )

        return {
            "current_volume": round(last_volume, 8),
            "average_volume": round(average_volume, 8),
            "volume_ratio": round(volume_ratio, 2),
            "volume_status": volume_status,
            "volume_signal": volume_signal,
            "volume_factors": factors,
        }

    def _validate_inputs(
        self,
        dataframe: pd.DataFrame,
        lookback: int,
        high_volume_threshold: float,
        low_volume_threshold: float,
    ) -> None:
        if dataframe.empty:
            raise ValueError(
                "Il dataframe non può essere vuoto."
            )

        if "volume" not in dataframe.columns:
            raise ValueError(
                "La colonna 'volume' non è presente nel dataframe."
            )

        if len(dataframe) < 2:
            raise ValueError(
                "Servono almeno due candele per analizzare il volume."
            )

        if lookback < 1:
            raise ValueError(
                "Il lookback deve essere almeno 1."
            )

        if high_volume_threshold <= 1:
            raise ValueError(
                "La soglia del volume alto deve essere maggiore di 1."
            )

        if not 0 < low_volume_threshold < 1:
            raise ValueError(
                "La soglia del volume basso deve essere compresa tra 0 e 1."
            )

        if low_volume_threshold >= high_volume_threshold:
            raise ValueError(
                "La soglia bassa deve essere inferiore alla soglia alta."
            )