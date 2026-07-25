import json
from datetime import datetime, timezone
from pathlib import Path

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
        """Restituisce tutti gli eventi registrati."""

        return self._load_journal()

    def get_closed_trades(
        self,
    ) -> list[dict]:
        """Restituisce i trade chiusi presenti nel Journal."""

        events = self._load_journal()

        closed_trades = [
            event
            for event in events
            if event.get("event") == "TRADE_CLOSED"
            and isinstance(event.get("data"), dict)
        ]

        closed_trades.sort(
            key=lambda event: event.get("timestamp", ""),
            reverse=True,
        )

        return closed_trades

    def get_recent_closed_trades(
        self,
        limit: int = 5,
    ) -> list[dict]:
        """Restituisce gli ultimi trade chiusi."""

        if limit <= 0:
            return []

        closed_trades = self.get_closed_trades()

        return closed_trades[:limit]

    def get_trade_events(
        self,
        trade_id: str,
    ) -> list[dict]:
        """Restituisce tutti gli eventi relativi a un trade."""

        events = self._load_journal()

        trade_events = [
            event
            for event in events
            if event.get("trade_id") == trade_id
        ]

        trade_events.sort(
            key=lambda event: event.get("timestamp", "")
        )

        return trade_events

    def log_event(
        self,
        trade_id: str,
        event_type: str,
        data: dict,
    ) -> None:
        """Registra un evento relativo a un trade."""

        journal = self._load_journal()

        event = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "trade_id": trade_id,
            "event": event_type,
            "data": data,
        }

        journal.append(event)

        self._save_journal(journal)