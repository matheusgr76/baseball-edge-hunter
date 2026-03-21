"""
MLB Edge Hunter - Entry Point

Live pipeline:
  python main.py

Historical backtest:
  python main.py --backtest --season 2024
  python main.py --backtest --season 2023 --max-dates 50 --spread 0.0
"""

import argparse


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MLB Edge Hunter")
    parser.add_argument(
        "--backtest",
        action="store_true",
        help="Run in historical backtest mode instead of live pipeline.",
    )
    parser.add_argument(
        "--season",
        type=int,
        default=2024,
        help="MLB season year to backtest (default: 2024).",
    )
    parser.add_argument(
        "--max-dates",
        type=int,
        default=30,
        help="Max game-dates to process per season (API quota guard, default: 30).",
    )
    parser.add_argument(
        "--spread",
        type=float,
        default=0.0,
        help="Simulated Polymarket spread vs bookmaker consensus in pp (default: 0.0).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.backtest:
        from backtesting.backtester import run_backtest
        run_backtest(
            season=args.season,
            max_dates=args.max_dates,
            poly_spread_pp=args.spread,
        )
    else:
        from orchestration.pipeline import run_pipeline
        run_pipeline()
