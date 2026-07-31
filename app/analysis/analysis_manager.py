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

    def analyze(self, symbol: str) -> dict:
        """Esegue l'analisi completa della crypto richiesta."""

        dataframe = self.market_data_service.get_candles(
            symbol=symbol,
            timeframe="1h",
            limit=100,
        )

        trend_result = self.trend_analyzer.analyze(
            symbol=symbol,
            dataframe=dataframe,
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

        score = self.score_calculator.calculate(
          trend=trend_result["trend"],
          trend_strength=trend_result["strength"],
          rsi=rsi_value,
          action=decision["action"],
          macd_status=macd_result["macd_status"],
          atr_percentage=atr_result["atr_percentage"],
          market_regime=market_regime["market_regime"],
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