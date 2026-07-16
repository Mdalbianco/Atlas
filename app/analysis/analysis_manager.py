from app.analysis.trend import TrendAnalyzer
from app.analysis.score import ScoreCalculator


class AnalysisManager:

    def __init__(self):

        self.trend = TrendAnalyzer()
        self.score = ScoreCalculator()

    def analyze(self, symbol: str):

        trend = self.trend.analyze(symbol)

        score = self.score.calculate(
            trend["strength"]
        )

        return {
            "symbol": symbol,
            "trend": trend["trend"],
            "score": score
        }