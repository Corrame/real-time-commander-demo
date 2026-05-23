from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from game.mirror_map_sim import POLICIES, run_batch, simulate_mirror_battle


def print_single(seed: int, jitter: int, red_policy: str, blue_policy: str) -> None:
    result = simulate_mirror_battle(seed=seed, jitter=jitter, red_policy=red_policy, blue_policy=blue_policy)
    print("mode=mirror-3v3-map")
    print(f"seed={seed}")
    print(f"jitter={jitter}")
    print(f"red_policy={red_policy}")
    print(f"blue_policy={blue_policy}")
    print(f"winner={result.winner}")
    print(f"ticks={result.ticks}")
    print(f"red_hp={result.red_hp}")
    print(f"blue_hp={result.blue_hp}")
    print(f"red_alive={result.red_alive}")
    print(f"blue_alive={result.blue_alive}")


def print_batch(runs: int, seed: int, jitter: int, red_policy: str, blue_policy: str) -> None:
    stats = run_batch(runs=runs, seed=seed, jitter=jitter, red_policy=red_policy, blue_policy=blue_policy)
    print("mode=mirror-3v3-map")
    print(f"runs={stats.runs}")
    print(f"jitter={jitter}")
    print(f"red_policy={red_policy}")
    print(f"blue_policy={blue_policy}")
    print(f"red_wins={stats.red_wins} ({stats.red_win_rate:.1%})")
    print(f"blue_wins={stats.blue_wins} ({stats.blue_win_rate:.1%})")
    print(f"draws={stats.draws} ({stats.draw_rate:.1%})")
    print(f"avg_ticks={stats.avg_ticks:.2f}")
    print(f"avg_red_hp={stats.avg_red_hp:.2f}")
    print(f"avg_blue_hp={stats.avg_blue_hp:.2f}")
    print(f"avg_winner_hp={stats.avg_winner_hp:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the mirrored 3v3 small-map baseline simulation.")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--jitter", type=int, default=0, help="Symmetric damage jitter. Default: 0")
    parser.add_argument("--red-policy", choices=sorted(POLICIES), default="dumb")
    parser.add_argument("--blue-policy", choices=sorted(POLICIES), default="dumb")
    args = parser.parse_args()

    if args.runs <= 0:
        parser.error("--runs must be greater than 0")

    if args.runs <= 1:
        print_single(args.seed, args.jitter, args.red_policy, args.blue_policy)
    else:
        print_batch(args.runs, args.seed, args.jitter, args.red_policy, args.blue_policy)


if __name__ == "__main__":
    main()
