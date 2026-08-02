class AnalysisReport:
    """Trasforma i risultati dell'analisi in un report leggibile."""

    def generate(self, result: dict) -> str:
        reasons = result.get("reasons", [])

        reasons_text = "\n".join(
            f"• {reason}"
            for reason in reasons
        )

        if not reasons_text:
            reasons_text = "• Nessuna motivazione disponibile"

        score = result.get("score", 0)

        score_classification = result.get(
            "score_classification",
            "Non classificato",
        )

        score_acceptable = result.get(
            "score_acceptable",
            False,
        )

        score_status = (
            "✅ Sì"
            if score_acceptable
            else "❌ No"
        )

        confidence = result.get("confidence", 0)

        confidence_classification = result.get(
         "confidence_classification",
         "Non classificata",
        )

        confidence_factors = result.get(
         "confidence_factors",
         [],
        )

        confidence_text = "\n".join(
         f"• {factor}"
         for factor in confidence_factors
        )

        if not confidence_text:
         confidence_text = "• Nessun fattore disponibile"

        market_regime = result.get(
         "market_regime",
         "Non classificato",
        )

        market_regime_score = result.get(
         "market_regime_score",
         0,
        )

        market_regime_factors = result.get(
         "market_regime_factors",
         [],
        )

        market_regime_text = "\n".join(
         f"• {factor}"
         for factor in market_regime_factors
        )

        if not market_regime_text:
         market_regime_text = "• Nessun fattore disponibile"

        lower_timeframe_trend = result.get(
            "lower_timeframe_trend",
            "Non disponibile",
        )

        higher_timeframe_trend = result.get(
            "higher_timeframe_trend",
            "Non disponibile",
        )

        timeframe_alignment = result.get(
            "timeframe_alignment",
            "Non classificato",
        )

        timeframe_alignment_score = result.get(
            "timeframe_alignment_score",
            0,
        )

        timeframe_aligned = result.get(
            "timeframe_aligned",
            False,
        )

        timeframe_status = (
            "✅ Sì"
            if timeframe_aligned
            else "❌ No"
        )

        timeframe_factors = result.get(
            "timeframe_factors",
            [],
        )

        timeframe_factors_text = "\n".join(
            f"• {factor}"
            for factor in timeframe_factors
        )

        if not timeframe_factors_text:
            timeframe_factors_text = "• Nessun fattore disponibile"

        report = (
            "📊 ATLAS ANALYSIS\n\n"
            f"🪙 Coppia: {result['symbol']}\n\n"
            f"💰 Prezzo: {result['current_price']:.2f} €\n\n"
            f"📈 Trend: {result['trend']}\n"
            f"💪 Forza trend: {result['strength']}\n\n"
            f"📉 RSI: {float(result['rsi']):.2f}\n"
            f"🔍 Segnale RSI: {result['rsi_signal']}\n\n"
            f"〽️ MACD: {result['macd']:.4f}\n"
            f"📊 Stato MACD: {result['macd_status']}\n\n"
            f"🌡️ ATR: {result['atr']:.4f}\n"
            f"🌪️ Volatilità: {result['volatility']} "
            f"({result['atr_percentage']:.2f}%)\n\n"
            f"🌍 Regime di mercato: {market_regime}\n"
            f"🕐 Trend 1H: {lower_timeframe_trend}\n"
            f"🕓 Trend 4H: {higher_timeframe_trend}\n"
            f"🤝 Allineamento: {timeframe_alignment}\n"
            f"📊 Score timeframe: {timeframe_alignment_score}/100\n"
            f"🛡️ Timeframe compatibili: {timeframe_status}\n"
            f"🔎 Fattori timeframe:\n"
            f"{timeframe_factors_text}\n\n"
            f"📊 Score regime: {market_regime_score}/100\n"
            f"🔎 Fattori del regime:\n"
            f"{market_regime_text}\n\n"
            f"⭐ Qualità setup: {score}/100\n"
            f"🏅 Classificazione: {score_classification}\n"
            f"🛡️ Setup accettabile: {score_status}\n\n"
            f"🤖 Confidenza Atlas: {confidence}/100\n"
            f"📊 Livello: {confidence_classification}\n"
            f"🧠 Fattori:\n"
            f"{confidence_text}\n\n"
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
                "⚖️ Rischio/Rendimento: "
                f"1:{result['risk_reward_ratio']:.1f}"
            )
        else:
            report += (
                "\n\n"
                "⏳ Nessun piano operativo disponibile."
            )

        return report