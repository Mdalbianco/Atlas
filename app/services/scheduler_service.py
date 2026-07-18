import time

from app.services.trade_monitor_service import TradeMonitorService


class SchedulerService:
    """Esegue periodicamente i servizi automatici di Atlas."""

    def __init__(self, interval_seconds: int = 60) -> None:
        self.interval_seconds = interval_seconds
        self.trade_monitor_service = TradeMonitorService()

    def run_once(self) -> list[dict]:
        """Esegue un singolo ciclo dello scheduler."""

        return self.trade_monitor_service.check_once()

    def run_forever(self) -> None:
        """Esegue continuamente il monitoraggio dei trade."""

        print(
            f"Scheduler avviato. "
            f"Controllo ogni {self.interval_seconds} secondi."
        )

        while True:
            try:
                closed_trades = self.run_once()

                if closed_trades:
                    print(f"Trade chiusi: {closed_trades}")
                else:
                    print("Nessun trade chiuso.")

            except Exception as error:
                print(f"Errore nello scheduler: {error}")

            time.sleep(self.interval_seconds)