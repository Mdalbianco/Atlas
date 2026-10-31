from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from atlas.config import Settings
from atlas.data.sources import SyntheticMarket


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # configurazione storica dei test: due strategie, senza cancello di validazione né book ombra
    return Settings(
        data_dir=tmp_path,
        cycle_interval_seconds=60,
        strategies=("trend_pullback", "breakout"),
        require_validation=False,
        shadow_strategies=False,
    )


@pytest.fixture(scope="session")
def market() -> SyntheticMarket:
    return SyntheticMarket(bars=2500, seed=7)


def make_df(closes, start_ms: int = 1_700_000_000_000, tf_ms: int = 3_600_000, volume=None, spread: float = 0.002) -> pd.DataFrame:
    closes = np.asarray(closes, dtype=float)
    opens = np.concatenate([[closes[0]], closes[:-1]])
    highs = np.maximum(opens, closes) * (1 + spread)
    lows = np.minimum(opens, closes) * (1 - spread)
    vol = np.full(len(closes), 100.0) if volume is None else np.asarray(volume, dtype=float)
    ts = start_ms + np.arange(len(closes), dtype="int64") * tf_ms
    return pd.DataFrame({"timestamp": ts, "open": opens, "high": highs, "low": lows, "close": closes, "volume": vol})


class Clock:
    def __init__(self, ms: int) -> None:
        self.ms = ms

    def __call__(self) -> datetime:
        return datetime.fromtimestamp(self.ms / 1000, tz=timezone.utc)
