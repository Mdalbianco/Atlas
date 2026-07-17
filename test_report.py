from app.analysis.analysis_manager import AnalysisManager
from app.analysis.report import AnalysisReport


def main() -> None:
    analysis_manager = AnalysisManager()
    report_generator = AnalysisReport()

    result = analysis_manager.analyze("BTC")
    report = report_generator.generate(result)

    print(report)


if __name__ == "__main__":
    main()