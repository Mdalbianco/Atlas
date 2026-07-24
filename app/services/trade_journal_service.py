import json
from pathlib import Path
from datetime import datetime


class TradeJournalService:
    """Gestisce lo storico degli eventi dei trade."""

    def __init__(
        self,
        file_path: str = "data/trade_journal.json",
    ) -> None:
        self.file_path = Path(file_path)

    def _load_journal(self) -> list[dict]:
        if not self.file_path.exists():
            return []

        with self.file_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    def _save_journal(
        self,
        journal: list[dict],
    ) -> None:

        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.file_path.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                journal,
                file,
                indent=4,
                ensure_ascii=False,
            )

    def get_all_events(self) -> list[dict]:
        return self._load_journal()

    def log_event(
        self,
        trade_id: str,
        event_type: str,
        data: dict,
    ) -> None:
        """Registra un evento relativo ad un trade."""

        journal = self._load_journal()

        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "trade_id": trade_id,
            "event": event_type,
            "data": data,
        }

        journal.append(event)

        self._save_journal(journal)