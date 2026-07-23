import json
from pathlib import Path
from datetime import datetime, timezone


class WalletService:
    """Gestisce il portafoglio virtuale di Atlas."""

    def __init__(self):
        self.wallet_file = Path("data/paper_wallet.json")

    def _load_wallet(self) -> dict:
        with open(self.wallet_file, "r", encoding="utf-8") as file:
            return json.load(file)

    def _save_wallet(self, wallet: dict) -> None:
        wallet["updated_at"] = datetime.now(
            timezone.utc
        ).isoformat()

        with open(self.wallet_file, "w", encoding="utf-8") as file:
            json.dump(wallet, file, indent=4)

    def get_balance(self) -> float:
        wallet = self._load_wallet()
        return wallet["current_balance"]

    def get_wallet(self) -> dict:
        return self._load_wallet()
    
    def get_total_profit(self) -> float:
     wallet = self._load_wallet()

     total_profit = (
        wallet["current_balance"]
        - wallet["initial_balance"]
    )

     return round(total_profit, 2)


    def get_roi(self) -> float:
     wallet = self._load_wallet()

     initial_balance = wallet["initial_balance"]

     if initial_balance == 0:
        return 0.0

     roi = (
        (
            wallet["current_balance"]
            - initial_balance
        )
        / initial_balance
    ) * 100

     return round(roi, 2)
    
    def apply_trade_result(
     self,
     performance_percentage: float,
     position_size: float,
    ) -> dict:
     """
     Aggiorna il saldo in base al risultato percentuale
     applicato alla dimensione della posizione.
     """

     wallet = self._load_wallet()

     profit_loss = (
        position_size * performance_percentage
    ) / 100

     wallet["current_balance"] += profit_loss

     self._save_wallet(wallet)

     return {
        "profit_loss": profit_loss,
        "current_balance": wallet["current_balance"],
        "performance_percentage": performance_percentage,
        "position_size": position_size,
    }