import json
from pathlib import Path


class WatchlistService:
    """Gestisce la lista delle criptovalute monitorate."""

    def __init__(self) -> None:
        self.file_path = Path("data/watchlist.json")
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Crea il file della watchlist se non esiste."""

        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.file_path.exists():
            self._save_symbols([])

    def _load_symbols(self) -> list[str]:
        """Legge le crypto salvate nel file JSON."""

        try:
            with self.file_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

        except (json.JSONDecodeError, OSError):
            return []

        symbols = data.get("symbols", [])

        return [
            str(symbol).upper()
            for symbol in symbols
        ]

    def _save_symbols(
        self,
        symbols: list[str],
    ) -> None:
        """Salva la watchlist nel file JSON."""

        data = {
            "symbols": sorted(set(symbols))
        }

        with self.file_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                indent=2,
            )

    def get_symbols(self) -> list[str]:
        """Restituisce la watchlist attuale."""

        return self._load_symbols()

    def add_symbol(self, symbol: str) -> bool:
        """Aggiunge una crypto. Restituisce False se era già presente."""

        symbol = symbol.upper()
        symbols = self._load_symbols()

        if symbol in symbols:
            return False

        symbols.append(symbol)
        self._save_symbols(symbols)

        return True

    def remove_symbol(self, symbol: str) -> bool:
        """Rimuove una crypto. Restituisce False se non era presente."""

        symbol = symbol.upper()
        symbols = self._load_symbols()

        if symbol not in symbols:
            return False

        symbols.remove(symbol)
        self._save_symbols(symbols)

        return True