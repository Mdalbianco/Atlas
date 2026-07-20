import time

from app.services.watchlist_service import WatchlistService

from app.services.auto_trade_service import AutoTradeService

from app.services.trade_monitor_service import TradeMonitorService


class SchedulerService:
    """Esegue periodicamente i servizi automatici di Atlas."""

    def __init__(self, interval_seconds: int = 60) -> None:
     self.interval_seconds = interval_seconds
     self.trade_monitor_service = TradeMonitorService()
     self.auto_trade_service = AutoTradeService()
     self.watchlist_service = WatchlistService()

    def run_once(self, symbols: list[str] | None = None) -> dict:
     """
     Esegue un ciclo completo:

     1. Controlla e chiude eventuali trade aperti.
     2. Analizza i simboli indicati.
     3. Apre eventuali nuovi trade simulati.
     """
    
     if symbols is None:
         symbols = self.watchlist_service.get_symbols()

     closed_trades = self.trade_monitor_service.check_once()
     auto_trade_results = []

     for symbol in symbols:
         existing_trade = (
            self.trade_monitor_service
            .paper_trading_service
            .get_open_trade(symbol)
        )

         if existing_trade is not None:
             auto_trade_results.append(
                {
                 "symbol": symbol.upper(),
                 "status": "already_open",
                 "action": "skip_analysis",
                 "reason": "Trade già aperto. Analisi saltata.",
                 "trade": existing_trade,
                }
            )
             continue

         result = self.auto_trade_service.analyze_and_open(symbol)
         auto_trade_results.append(result)

     return {
         "closed_trades": closed_trades,
         "auto_trade_results": auto_trade_results,
    }

    def run_forever(self) -> None:
     """Esegue continuamente il ciclo completo di Atlas."""

     print(
         f"Scheduler Atlas avviato. "
         f"Controllo ogni {self.interval_seconds} secondi."
        )

     while True:
        try:
            result = self.run_once()

            closed_trades = result["closed_trades"]
            auto_trade_results = result["auto_trade_results"]

            if closed_trades:
                print(f"Trade chiusi: {len(closed_trades)}")
            else:
                print("Nessun trade chiuso.")

            print(f"Simboli elaborati: {len(auto_trade_results)}")

            for item in auto_trade_results:
                symbol = item.get("symbol")

                if item.get("status") == "already_open":
                 print(f"{symbol}: trade già aperto — analisi saltata")
                 continue

                if item.get("trade_opened"):
                 trade = item["trade"]

                 print(
                     f"{trade['symbol']}: nuovo trade "
                     f"{trade['direction']} aperto"
                )
                 continue
            
                analysis = item.get("analysis", {})
                action = analysis.get("action", "Attendere")
                reasons = analysis.get("reasons", [])

                reason_text = (
                 ", ".join(reasons)
                 if reasons
                 else item.get("reason", "Nessun dettaglio")
                )

                analysis_symbol = analysis.get("symbol", symbol or "?")
                clean_symbol = analysis_symbol.replace("/EUR", "")

                print(
                 f"{clean_symbol}: {action} — {reason_text}"
                )

            print("-" * 40)

        except KeyboardInterrupt:
            print("\nScheduler fermato manualmente.")
            break

        except Exception as error:
            print(f"Errore nello scheduler: {error}")

        time.sleep(self.interval_seconds)