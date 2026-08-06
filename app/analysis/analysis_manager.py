from app.risk.risk_manager import RiskManager
from app.analysis.atr import ATRAnalyzer
from app.analysis.decision import DecisionEngine
from app.analysis.macd import MACDAnalyzer
from app.analysis.rsi import RSIAnalyzer
from app.analysis.score import ScoreCalculator
from app.analysis.trend import TrendAnalyzer
from app.services.market_data_service import MarketDataService
from app.analysis.confidence import ConfidenceCalculator
from app.analysis.market_regime import MarketRegimeDetector
from app.analysis.multi_timeframe import MultiTimeframeAnalyzer
from app.analysis.support_resistance import SupportResistanceAnalyzer
from app.analysis.candle_context import CandleContextAnalyzer


class AnalysisManager:
    """Coordina i moduli di analisi di Atlas."""

    def __init__(self) -> None:
        self.decision_engine = DecisionEngine()
        self.market_data_service = MarketDataService()
        self.trend_analyzer = TrendAnalyzer()
        self.rsi_analyzer = RSIAnalyzer()
        self.macd_analyzer = MACDAnalyzer()
        self.score_calculator = ScoreCalculator()
        self.confidence_calculator = ConfidenceCalculator()
        self.market_regime_detector = MarketRegimeDetector()
        self.multi_timeframe_analyzer = MultiTimeframeAnalyzer()
        self.support_resistance_analyzer = SupportResistanceAnalyzer()
        self.candle_context_analyzer = CandleContextAnalyzer()

    def analyze(self, symbol: str) -> dict:
        """Esegue l'analisi completa della crypto richiesta."""

        dataframe = self.market_data_service.get_candles(
            symbol=symbol,
            timeframe="1h",
            limit=100,
        )

        higher_dataframe = self.market_data_service.get_candles(
            symbol=symbol,
            timeframe="4h",
            limit=100,
        )

        trend_result = self.trend_analyzer.analyze(
            symbol=symbol,
            dataframe=dataframe,
        )

        higher_trend_result = self.trend_analyzer.analyze(
            symbol=symbol,
            dataframe=higher_dataframe,
        )

        rsi_value = self.rsi_analyzer.calculate(
            dataframe["close"]
        )

        rsi_signal = self.rsi_analyzer.get_signal(
            rsi_value
        )

        macd_result = self.macd_analyzer.calculate(
            dataframe["close"]
        )

        atr_analyzer = ATRAnalyzer()
        atr_result = atr_analyzer.calculate(dataframe)

        candle_context = self.candle_context_analyzer.analyze(
            dataframe=dataframe,
            atr=atr_result["atr"],
        )

        support_resistance = self.support_resistance_analyzer.analyze(
            dataframe=dataframe,
            current_price=trend_result["current_price"],
        )

        market_regime = self.market_regime_detector.detect(
         trend=trend_result["trend"],
         trend_strength=trend_result["strength"],
         atr_percentage=atr_result["atr_percentage"],
         rsi=rsi_value,
         macd_status=macd_result["macd_status"],
        )

        decision = self.decision_engine.analyze(
         trend=trend_result["trend"],
         rsi=rsi_value,
         macd_status=macd_result["macd_status"],
        )

        multi_timeframe = self.multi_timeframe_analyzer.analyze(
            lower_trend=trend_result["trend"],
            lower_strength=trend_result["strength"],
            higher_trend=higher_trend_result["trend"],
            higher_strength=higher_trend_result["strength"],
            action=decision["action"],
        )

        score = self.score_calculator.calculate(
            trend=trend_result["trend"],
            trend_strength=trend_result["strength"],
            rsi=rsi_value,
            action=decision["action"],
            macd_status=macd_result["macd_status"],
            atr_percentage=atr_result["atr_percentage"],
            market_regime=market_regime["market_regime"],
            timeframe_alignment_score=multi_timeframe[
                "timeframe_alignment_score"
            ],
            timeframe_aligned=multi_timeframe[
                "timeframe_aligned"
            ],
            near_support=support_resistance["near_support"],
            near_resistance=support_resistance["near_resistance"],
        )

        score_classification = self.score_calculator.classify(
          score
        )

        score_acceptable = self.score_calculator.is_acceptable(
            score=score,
            minimum_score=65,
        )

        confidence = self.confidence_calculator.calculate(
            score=score,
            action=decision["action"],
            trend=trend_result["trend"],
            macd_status=macd_result["macd_status"],
            rsi=rsi_value,
            atr_percentage=atr_result["atr_percentage"],
            market_regime=market_regime["market_regime"],
            timeframe_alignment_score=multi_timeframe[
                "timeframe_alignment_score"
            ],
            timeframe_aligned=multi_timeframe[
                "timeframe_aligned"
            ],
        )
        
        risk_manager = RiskManager()
        trade_result = risk_manager.calculate_trade_levels(
            current_price=trend_result["current_price"],
            atr=atr_result["atr"],
            action=decision["action"],
        )

        return {
         **confidence,
         **market_regime,
         **multi_timeframe,
         **support_resistance,
         **candle_context,
         **trend_result,
         "rsi": rsi_value,
         "rsi_signal": rsi_signal,
         **macd_result,
         **decision,
         "score": score,
         "score_classification": score_classification,
         "score_acceptable": score_acceptable,
         "atr": atr_result["atr"],
         "atr_percentage": atr_result["atr_percentage"],
         "volatility": atr_result["volatility"],
         **trade_result,
        }