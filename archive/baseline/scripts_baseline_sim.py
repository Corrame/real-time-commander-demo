from __future__ import annotations

import argparse
import sys
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ARCHIVED — this script requires game.baseline_sim which was also archived.
# The code was moved to archive/baseline/ as part of refactoring.
# It no longer runs from the main project path; kept for reference.

from game.baseline_sim import CONFIGS, run_batch, simulate_battle


def print_single(config_key: str, seed: int) -> None:
    config = CONFIGS[config_key]
    result = simulate_battle(config, random.Random(seed))
    print(f"config={config.name}")
    print(f"seed={seed}")
    print(f"winner={result.winner}")
    print(f"rounds={result.rounds}")
    print(f"friendly_hp={result.friendly_hp}")
    print(f"enemy_hp={result.enemy_hp}")


def print_batch(config_key: str, runs: int, seed: int) -> None:
    config = CONFIGS[config_key]
    stats = run_batch(config, runs, seed)
    print(f"config={stats.config_name}")
    print(f"runs={stats.runs}")
    print(f"friendly_wins={stats.friendly_wins} ({stats.friendly_win_rate:.1%})")
    print(f"enemy_wins={stats.enemy_wins} ({stats.enemy_win_rate:.1%})")
    print(f"draws={stats.draws} ({stats.draw_rate:.1%})")
    print(f"avg_rounds={stats.avg_rounds:.2f}")
    print(f"avg_friendly_hp={stats.avg_friendly_hp:.2f}")
    print(f"avg_enemy_hp={stats.avg_enemy_hp:.2f}")
    print(f"avg_winner_hp={stats.avg_winner_hp:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run calibrated 0.1/0.2 baseline battle simulations.")
    parser.add_argument("--config", choices=sorted(CONFIGS), default="0.1")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.runs <= 1:
        print_single(args.config, args.seed)
    else:
        print_batch(args.config, args.runs, args.seed)


if __name__ == "__main__":
    main()
