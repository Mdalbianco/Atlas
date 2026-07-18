import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class PaperTradingService:
    """Gestisce le operazioni simulate di Atlas."""

    def __init__(
        self,
        file_path: str = "data/paper_trades.json",
    ) -> None:
        self.file_path = Path(file_path)

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

    def get_open_trade(
        self,
        symbol: str,
    ) -> dict | None:
      """Restituisce il trade aperto per il simbolo, se esiste."""
      
      trades = self._load_trades()
      
      symbol = symbol.upper()
      
      for trade in trades:
        if (
            trade["symbol"] == symbol
            and trade["status"] == "open"
        ):
         return trade
        
        return None
    def get_open_trades(
     self,
    ) -> list[dict]:
     """Restituisce tutti i trade aperti."""

     trades = self._load_trades()
     
     return [
         trade
         for trade in trades
         if trade["status"] == "open"
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

             closed_trade = self.check_trade_exit(
                trade=trade,
                current_price=current_price,
            )
             
             if closed_trade is not None:
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
    ) -> dict:
        
        existing_trade = self.get_open_trade(symbol)
        
        if existing_trade is not None:
           return existing_trade
        trades = self._load_trades()

        trade = {
            "id": str(uuid4()),
            "symbol": symbol.upper(),
            "direction": direction,
            "entry_price": entry_price,
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

        return trade