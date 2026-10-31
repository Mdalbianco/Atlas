"""Interfaccia a riga di comando di ATLAS.

Esempi:
    python -m atlas run                       # bot + scheduler (paper trading)
    python -m atlas cycle                     # un singolo ciclo e poi esce
    python -m atlas analyze BTC               # analisi di una coppia
    python -m atlas status                    # stato del conto simulato
    python -m atlas healthcheck               # 0 se il sistema è vivo (per Docker/systemd)
    python -m atlas download BTC/EUR --days 30 --out data/history/BTC_EUR_1h.csv
    python -m atlas backtest --csv data/history/BTC_EUR_1h.csv
    python -m atlas backtest --synthetic --walk-forward
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _settings():
    from atlas.config import load_settings
    from atlas.logging_setup import register_secret, setup_logging

    s = load_settings()
    setup_logging(s.log_level, s.log_json)
    for secret in (s.telegram_token, s.kraken_api_key, s.kraken_api_secret):
        register_secret(secret)
    return s


def cmd_run(args) -> int:
    from atlas.app import Atlas
    from atlas.runner import run_forever

    run_forever(Atlas(_settings()))
    return 0


def cmd_cycle(args) -> int:
    from atlas.app import Atlas

    atlas = Atlas(_settings())
    rep = atlas.cycle.run_once()
    print(json.dumps({"ok": rep.ok, "analyzed": rep.analyzed, "decisions": rep.decisions, "opened": len(rep.opened), "closed": len(rep.closed), "errors": rep.errors, "equity": rep.equity}, ensure_ascii=False, indent=2))
    return 0 if rep.ok else 1


def cmd_analyze(args) -> int:
    from atlas.app import Atlas

    print(Atlas(_settings()).text_analysis(args.symbol))
    return 0


def cmd_status(args) -> int:
    from atlas.app import Atlas

    atlas = Atlas(_settings())
    print(atlas.text_status())
    print()
    print(atlas.text_performance())
    return 0


def cmd_healthcheck(args) -> int:
    from atlas.config import load_settings
    from atlas.storage.db import Database

    s = load_settings()
    if not s.db_path.exists():
        print("database non trovato")
        return 1
    db = Database(s.db_path)
    hb = db.get_state("heartbeat")
    if not hb:
        print("nessun heartbeat")
        return 1
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(hb)).total_seconds()
    ok = age < 3 * s.cycle_interval_seconds + 120
    print(f"heartbeat {age:.0f}s fa — {'OK' if ok else 'NON AGGIORNATO'}; halted={db.get_state('halted', False)}")
    return 0 if ok else 1


def cmd_download(args) -> int:
    from atlas.data.exchange import KrakenDataSource
    from atlas.data.market_data import download_history, now_ms

    src = KrakenDataSource()
    since = now_ms() - args.days * 86_400_000
    df = download_history(src, args.symbol.upper(), args.timeframe, since)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"{len(df)} candele salvate in {out}. Nota: l'API OHLC di Kraken fornisce solo le ultime ~720 candele; per storici lunghi usare i file OHLCVT ufficiali Kraken (vedi docs/BACKTESTING.md).")
    return 0


def symbol_from_filename(path: str) -> str:
    """BTC_EUR_1h.csv → BTC/EUR ; XBTEUR_60.csv (file Kraken) → BTC/EUR."""
    parts = Path(path).stem.upper().split("_")
    if len(parts) >= 2 and parts[0].isalpha() and parts[1].isalpha():
        base, quote = parts[0], parts[1]
    else:
        pair = parts[0]
        base, quote = pair[:-3], pair[-3:]
    base = {"XBT": "BTC", "XXBT": "BTC", "XETH": "ETH", "XDG": "DOGE"}.get(base, base)
    quote = {"ZEUR": "EUR", "ZUSD": "USD"}.get(quote, quote)
    return f"{base}/{quote}"


def cmd_backtest(args) -> int:
    from atlas.backtest.engine import Backtester, BacktestConfig
    from atlas.backtest.metrics import format_report, full_report
    from atlas.backtest.walkforward import validate, walk_forward
    from atlas.config import load_settings, normalize_symbol
    from atlas.data.sources import SyntheticMarket, load_csv
    from atlas.engine.position_manager import ManagementParams
    from atlas.risk.costs import CostModel
    from atlas.risk.manager import RiskLimits
    from atlas.strategy.registry import build_strategies

    s = load_settings()
    if args.synthetic:
        data = SyntheticMarket(bars=args.bars, seed=args.seed).data
        print("⚠️ Dati SINTETICI: verificano la meccanica del sistema, non la redditività reale.\n")
    else:
        if not args.csv:
            print("Specifica --csv FILE [FILE...] (uno per coppia) oppure --synthetic")
            return 2
        data = {}
        for item in args.csv:
            sym, path = item.split("=", 1) if "=" in item else (symbol_from_filename(item), item)
            data[normalize_symbol(sym, s.quote_currency)] = load_csv(path)
    strategies = args.strategies.split(",") if args.strategies else list(s.strategies)
    cfg = BacktestConfig(
        initial_capital=s.initial_capital,
        timeframe=s.timeframe,
        higher_timeframe=s.higher_timeframe,
        min_score=s.min_score,
        spread_pct=s.default_spread_pct,
        costs=CostModel(s.taker_fee_pct, s.slippage_pct, s.default_spread_pct),
        limits=RiskLimits.from_settings(s),
        management=ManagementParams(s.trailing_activation_r, s.trailing_atr_multiple, s.time_stop_bars),
        market_symbol=s.market_reference if s.market_reference in data else None,
    )
    if args.walk_forward:
        wf = walk_forward(data, cfg, strategies, train_bars=args.train_bars, test_bars=args.test_bars)
        print("WALK-FORWARD (risultati fuori campione)")
        for i, f in enumerate(wf["folds"], 1):
            t = f["test"]
            print(f" fold {i}: parametri {f['params']} → test {t['net_return_pct']:+.2f}% ({t['trades'].get('trades', 0)} op.), buy&hold {t['benchmark_buy_hold_return_pct']:+.2f}%")
        print(f"Totale OOS: {wf['oos']}")
        print(f"Stabilità parametri: {wf['param_stability']}")
        out = wf
    elif args.validate:
        out = validate(data, cfg, strategies)
        print("VALIDAZIONE train/validazione/test — parametri scelti sul training:", out["best_params"])
        for k in ("train", "validation", "test"):
            print(f"\n== {k.upper()} ==")
            print(format_report(out[k]))
        print("\nAvvertenze:\n" + "\n".join(f"- {w}" for w in out["warnings"]))
    else:
        res = Backtester(build_strategies(strategies), cfg).run(data)
        out = full_report(res)
        print(format_report(out))
    if args.json:
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"\nReport JSON salvato in {args.json}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atlas", description="ATLAS — analisi e paper trading crypto")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="avvia bot Telegram e scheduler").set_defaults(func=cmd_run)
    sub.add_parser("cycle", help="esegue un singolo ciclo").set_defaults(func=cmd_cycle)
    p = sub.add_parser("analyze", help="analizza una coppia")
    p.add_argument("symbol")
    p.set_defaults(func=cmd_analyze)
    sub.add_parser("status", help="stato e performance").set_defaults(func=cmd_status)
    sub.add_parser("healthcheck", help="verifica heartbeat").set_defaults(func=cmd_healthcheck)
    p = sub.add_parser("download", help="scarica candele da Kraken in CSV")
    p.add_argument("symbol")
    p.add_argument("--timeframe", default="1h")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_download)
    p = sub.add_parser("backtest", help="backtest / validazione")
    p.add_argument("--csv", nargs="*", help="file CSV (nome tipo BTC_EUR_1h.csv) oppure SIMBOLO=percorso")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--bars", type=int, default=5000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--strategies")
    p.add_argument("--validate", action="store_true", help="split train/validazione/test")
    p.add_argument("--walk-forward", action="store_true")
    p.add_argument("--train-bars", type=int, default=2000)
    p.add_argument("--test-bars", type=int, default=500)
    p.add_argument("--json")
    p.set_defaults(func=cmd_backtest)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
