from app.analysis.score import ScoreCalculator
from app.analysis.trend import TrendAnalyzer


class AnalysisManager:
    """Coordina i moduli di analisi di Atlas."""

    def __init__(self) -> None:
        self.trend_analyzer = TrendAnalyzer()
        self.score_calculator = ScoreCalculator()

    def analyze(self, symbol: str) -> dict:
        """Esegue l'analisi completa della crypto richiesta."""

        trend_result = self.trend_analyzer.analyze(symbol)

        score = self.score_calculator.calculate(
            trend_result["strength"]
        )

        return {
            **trend_result,
            "score": score,
        }