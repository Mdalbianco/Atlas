import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from app.services.trade_journal_service import TradeJournalService

from app.services.notification_service import NotificationService
from app.services.wallet_service import WalletService

class PaperTradingService:
    """Gestisce le operazioni simulate di Atlas."""

    def __init__(
        self,
        file_path: str = "data/paper_trades.json",
    ) -> None:
        self.file_path = Path(file_path)
        self.notification_service = NotificationService()
        self.wallet_service = WalletService()
        self.trade_journal_service = TradeJournalService()

        self.trailing_stop_enabled = True
        self.trailing_activation_percentage = 2.0
        self.trailing_distance_percentage = 1.0

    def _load_trades(self) -> list[dict]:
        if not self.file_path.exists():
            return []

        with self.file_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    def _save_trades(
        self,
        trades: list[dict],
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
                trades,
                file,
                indent=4,
                ensure_ascii=False,
            )

    def get_open_trade(self, symbol: str) -> dict | None:
     """Restituisce il trade aperto per il simbolo indicato."""

     normalized_symbol = symbol.upper().replace("/EUR", "")
     trades = self._load_trades()

     for trade in trades:
         trade_symbol = str(
            trade.get("symbol", "")
        ).upper().replace("/EUR", "")

         if (
             trade_symbol == normalized_symbol
             and trade.get("status") == "open"
        ):
            return trade

     return None
      
    def get_open_trades(self) -> list[dict]:
     """
     Restituisce tutti i trade attualmente aperti.
     """

     trades = self._load_trades()

     return [
         trade
         for trade in trades
         if trade.get("status") == "open"
    ]
    
    def close_trade(
           self,
         trade_id: str,
         exit_price: float,
         result: str,
    ) -> dict | None:
        """Chiude un trade aperto."""
        
        trades = self._load_trades()
        
        for trade in trades:
            if (
             trade["id"] == trade_id
             and trade["status"] == "open"
            ):
               trade["status"] = "closed"
               trade["exit_price"] = exit_price
               trade["result"] = result
               trade["closed_at"] = datetime.now(
                 timezone.utc
                ).isoformat()

               self._save_trades(trades)

               return trade
        
        return None

    def update_trailing_stop(
        self,
        trade: dict,
        current_price: float,
    ) -> dict:
        """Aggiorna lo stop loss quando il trade è in profitto."""

        if not self.trailing_stop_enabled:
           return trade

        entry_price = float(trade["entry_price"])
        current_stop_loss = float(trade["stop_loss"])
        direction = trade["direction"]

        if entry_price <= 0:
            return trade

        if direction == "Long":
            performance_percentage = (
                (current_price - entry_price)
                / entry_price
            ) * 100

            if (
                performance_percentage
                < self.trailing_activation_percentage
            ):
                return trade

            new_stop_loss = current_price * (
                1 - self.trailing_distance_percentage / 100
            )

            if new_stop_loss <= current_stop_loss:
                return trade

        elif direction == "Short":
            performance_percentage = (
             (entry_price - current_price)
             / entry_price
            ) * 100

            if (
                performance_percentage
                < self.trailing_activation_percentage
            ):
                return trade

            new_stop_loss = current_price * (
                1 + self.trailing_distance_percentage / 100
            )

            if new_stop_loss >= current_stop_loss:
                return trade

        else:
            return trade

        trades = self._load_trades()

        for saved_trade in trades:
            if (
                saved_trade.get("id") == trade.get("id")
                and saved_trade.get("status") == "open"
            ):
                old_stop_loss = float(
                    saved_trade["stop_loss"]
                )

                saved_trade["stop_loss"] = round(
                    new_stop_loss,
                    8,
                )

                saved_trade["trailing_stop_active"] = True
                saved_trade["previous_stop_loss"] = old_stop_loss

                trade = saved_trade
                break

        self._save_trades(trades)

        return trade
    
    def check_trade_exit(
     self,
     trade: dict,
     current_price: float,
    ) -> dict | None:
       """Controlla se il trade deve essere chiuso."""
       
       direction = trade["direction"]
       
       if direction == "Long":

        if current_price <= trade["stop_loss"]:
           return self.close_trade(
                trade_id=trade["id"],
                exit_price=current_price,
                result="loss",
            )

        if current_price >= trade["take_profit"]:
            return self.close_trade(
                trade_id=trade["id"],
                exit_price=current_price,
                result="win",
            )
        
        elif direction == "Short":
            
            if current_price >= trade["stop_loss"]:
               return self.close_trade(
                 trade_id=trade["id"],
                 exit_price=current_price,
                 result="loss",
                )
            
            if current_price <= trade["take_profit"]:
               return self.close_trade(
                  trade_id=trade["id"],
                  exit_price=current_price,
                 result="win",
                )
        return None
       
    def check_open_trades(self, price_provider) -> list[dict]:
       """
       Controlla tutti i trade aperti.
       price_provider deve essere una funzione che riceve il simbolo
       e restituisce il prezzo corrente.
       """
       
       open_trades = self.get_open_trades()
       closed_trades = []
       
       for trade in open_trades:
          symbol = trade["symbol"]
          
          try:
             current_price = price_provider(symbol)

             previous_stop_loss = float(
                 trade["stop_loss"]
            )

             trade = self.update_trailing_stop(
                 trade=trade,
                 current_price=current_price,
            )

             updated_stop_loss = float(
                 trade["stop_loss"]
            )

             if updated_stop_loss != previous_stop_loss:
                 print(
                     f"{symbol}: trailing stop aggiornato "
                     f"da {previous_stop_loss:.2f} "
                     f"a {updated_stop_loss:.2f}"
                )

             closed_trade = self.check_trade_exit(
                  trade=trade,
                  current_price=current_price,
            )
             
             if closed_trade is not None:
                 entry_price = closed_trade["entry_price"]
                 exit_price = closed_trade["exit_price"]
                 direction = closed_trade["direction"]

                 if direction == "Long":
                     profit_percentage = (
                     (exit_price - entry_price) / entry_price
                    ) * 100
                 else:
                     profit_percentage = (
                     (entry_price - exit_price) / entry_price
                    ) * 100
                     
                 position_size = closed_trade.get("position_size", 20.0)

                 wallet_result = self.wallet_service.apply_trade_result(
                     performance_percentage=profit_percentage,
                     position_size=position_size,
                )

                 closed_trade["profit_percentage"] = round(
                 profit_percentage,
                 2,
                )
                 closed_trade["profit_loss"] = round(
                 wallet_result["profit_loss"],
                 2,
                )
                 closed_trade["wallet_balance"] = round(
                 wallet_result["current_balance"],
                 2,
                )
                 opened_at = datetime.fromisoformat(
                 closed_trade["opened_at"]
                )
                 closed_at = datetime.fromisoformat(
                 closed_trade["closed_at"]
                )

                 duration_seconds = int(
                 (closed_at - opened_at).total_seconds()
                )

                 duration_hours = duration_seconds // 3600
                 remaining_minutes = (duration_seconds % 3600) // 60
                 remaining_seconds = duration_seconds % 60

                 closed_trade["duration"] = (

                 f"{duration_hours}h "
                 f"{remaining_minutes}m "
                 f"{remaining_seconds}s"
                )

                 trades = self._load_trades()
                 for saved_trade in trades:
                     if saved_trade["id"] == closed_trade["id"]:
                         saved_trade.update(closed_trade)
                         break

                 self._save_trades(trades)
                 self.trade_journal_service.log_event(
                     trade_id=closed_trade["id"],
                     event_type="TRADE_CLOSED",
                     data=closed_trade,
                )
                 result_icon = (
                     "🎯 TAKE PROFIT"
                     if closed_trade["result"] == "win"
                     else "🛑 STOP LOSS"
                )

                 self.notification_service.send_sync(
                     f"{result_icon}\n\n"
                     f"Crypto: {closed_trade['symbol']}\n"
                     f"Direzione: {direction}\n\n"
                     f"Entrata: {entry_price:.2f} €\n"
                     f"Uscita: {exit_price:.2f} €\n\n"
                     f"Risultato: {closed_trade['result'].upper()}\n"
                     f"Performance: {profit_percentage:+.2f}%\n"
                     f"Durata: {duration_hours}h {remaining_minutes}m {remaining_seconds}s"
                )

                 closed_trades.append(closed_trade)
                
          except Exception as error:
             print(
                f"Errore durante il controllo del trade "
                f"{trade['id']} ({symbol}): {error}"
            )
        
       return closed_trades

    def open_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        position_size: float = 20.0,
    ) -> dict:
        
        symbol = symbol.upper().replace("/EUR", "")
        existing_trade = self.get_open_trade(symbol)
        
        if existing_trade is not None:
           return existing_trade
        trades = self._load_trades()

        trade = {
            "id": str(uuid4()),
            "symbol": symbol.upper(),
            "direction": direction,
            "entry_price": entry_price,
            "position_size": position_size,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "status": "open",
            "opened_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "closed_at": None,
            "exit_price": None,
            "result": None,
        }
        trades.append(trade)
        self._save_trades(trades)

        self.trade_journal_service.log_event(
        trade_id=trade["id"],
        event_type="TRADE_OPENED",
        data=trade,
        )
        return trade

