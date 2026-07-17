class AnalysisReport:
    """Trasforma i risultati dell'analisi in un report leggibile."""

    def generate(self, result: dict) -> str:
     reasons = result.get("reasons", [])

     reasons_text = "\n".join(
        f"• {reason}" for reason in reasons
    )

     if not reasons_text:
        reasons_text = "• Nessuna motivazione disponibile"

     report = (
         "📊 ATLAS ANALYSIS\n\n"
         f"💱 Coppia: {result['symbol']}\n\n"
         f"💰 Prezzo: {result['current_price']:.2f} €\n\n"
         f"📈 Trend: {result['trend']}\n"
         f"💪 Forza trend: {result['strength']}\n\n"
         f"📉 RSI: {float(result['rsi']):.2f}\n"
         f"🔎 Segnale RSI: {result['rsi_signal']}\n\n"
         f"〽️ MACD: {result['macd']:.4f}\n"
         f"📊 Stato MACD: {result['macd_status']}\n\n"
         f"🌡 ATR: {result['atr']:.4f}\n"
         f"🌪 Volatilità: {result['volatility']} "
         f"({result['atr_percentage']:.2f}%)\n\n"
         f"⭐ Score: {result['score']}/100\n\n"
         f"🧠 Decisione: {result['action']}\n"
         f"🎯 Decision score: {result['decision_score']}\n\n"
         "📋 Motivazioni:\n"
         f"{reasons_text}"
        )

     if result.get("trade_available"):
        report += (
            "\n\n"
            "⚙️ PIANO OPERATIVO\n\n"
            f"📍 Direzione: {result['trade_direction']}\n"
            f"💰 Ingresso: {result['entry_price']:.2f} €\n"
            f"🛑 Stop loss: {result['stop_loss']:.2f} €\n"
            f"🎯 Take profit: {result['take_profit']:.2f} €\n"
            f"⚖️ Rischio/Rendimento: "
            f"1:{result['risk_reward_ratio']:.1f}"
        )
     else:
        report += (
            "\n\n"
            "⏳ Nessun piano operativo disponibile."
        )

     return report