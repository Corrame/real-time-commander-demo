#!/usr/bin/env python3
"""自检：验证核心证据成立，不需要 LLM，纯规则底盘即可跑完。

用法：
    python3 scripts/self_check.py
    python3 scripts/self_check.py --runs 500  # 快速模式

跑完输出 PASS/FAIL。全 PASS 意味着代码底盘自洽。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from game.mirror_map_sim import POLICIES, run_batch

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

passes = 0
failures = 0


def ok(msg: str) -> None:
    global passes
    passes += 1
    print(f"  {GREEN}PASS{RESET} {msg}")


def fail(msg: str) -> None:
    global failures
    failures += 1
    print(f"  {RED}FAIL{RESET} {msg}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Self-check the 3v3 mirror sim evidence.")
    parser.add_argument("--runs", type=int, default=1000, help="Batch runs per check (default 1000)")
    args = parser.parse_args()
    runs = max(100, args.runs)

    print(f"Real-Time Commander Demo — 自检 (runs={runs})\n")

    # 1. 引擎不偏袒任一方
    print("[1] 镜像对称五五开 (dumb vs dumb)")
    s = run_batch(runs=runs, seed=42, jitter=1, red_policy="dumb", blue_policy="dumb")
    if abs(s.red_win_rate - s.blue_win_rate) < 0.15:
        ok(f"red {s.red_win_rate:.1%} / blue {s.blue_win_rate:.1%} — 对称")
    else:
        fail(f"red {s.red_win_rate:.1%} / blue {s.blue_win_rate:.1%} — 偏袒")

    # 2. 好指挥赢
    print("[2] 好指挥 vs 不指挥")
    s = run_batch(runs=runs, seed=42, jitter=1, red_policy="good_focus", blue_policy="dumb")
    if s.red_win_rate > 0.80:
        ok(f"red {s.red_win_rate:.1%} — 好指挥显著优于不指挥")
    else:
        fail(f"red {s.red_win_rate:.1%} — 好指挥没拉开差距")

    # 3. 莽夫必死
    print("[3] 莽夫 vs 不指挥")
    s = run_batch(runs=runs, seed=42, jitter=1, red_policy="bad_charge", blue_policy="dumb")
    if s.red_win_rate < 0.05:
        ok(f"red {s.red_win_rate:.1%} — 莽夫几乎必败")
    else:
        fail(f"red {s.red_win_rate:.1%} — 莽夫居然赢了")

    # 4. 趴下必死
    print("[4] 趴下 vs 不指挥")
    s = run_batch(runs=runs, seed=42, jitter=1, red_policy="cower_all", blue_policy="dumb")
    if s.red_win_rate < 0.01:
        ok(f"red {s.red_win_rate:.1%} — 趴下全灭")
    else:
        fail(f"red {s.red_win_rate:.1%} — 趴下居然赢了")

    # 5. 固守不吃亏
    print("[5] 固守 vs 不指挥")
    s = run_batch(runs=runs, seed=42, jitter=1, red_policy="hold_all", blue_policy="dumb")
    if s.red_win_rate > s.blue_win_rate:
        ok(f"red {s.red_win_rate:.1%} / blue {s.blue_win_rate:.1%} — 固守优于不指挥")
    else:
        fail(f"red {s.red_win_rate:.1%} / blue {s.blue_win_rate:.1%} — 固守没守住")

    # 6. 对手会打，差距还在
    print("[6] 好指挥 vs 会打的对手")
    s = run_batch(runs=runs, seed=42, jitter=1, red_policy="good_focus", blue_policy="good_focus")
    if abs(s.red_win_rate - s.blue_win_rate) < 0.05:
        ok(f"red {s.red_win_rate:.1%} / blue {s.blue_win_rate:.1%} — 同策略势均力敌")
    else:
        fail(f"red {s.red_win_rate:.1%} / blue {s.blue_win_rate:.1%} — 不对称")

    # 7. 不指挥被会打的抹平
    print("[7] 不指挥 vs 会打的对手")
    s = run_batch(runs=runs, seed=42, jitter=1, red_policy="dumb", blue_policy="good_focus")
    if s.red_win_rate < 0.01:
        ok(f"red {s.red_win_rate:.1%} — 不指挥被抹平")
    else:
        fail(f"red {s.red_win_rate:.1%} — 不指挥竟然能赢")

    # 8. jitter=0 时同归于尽
    print("[8] 零随机同归于尽")
    s = run_batch(runs=100, seed=42, jitter=0, red_policy="dumb", blue_policy="dumb")
    if s.draws == s.runs:
        ok(f"{s.draws}/{s.runs} 全平 — 确定性引擎正确")
    else:
        fail(f"red {s.red_win_rate:.1%} / blue {s.blue_win_rate:.1%} / draw {s.draw_rate:.1%} — 零随机未全平")

    # 9. 6 个 policy 全部合法
    expected = {"dumb", "good_focus", "bad_charge", "hold_all", "cower_all", "hesitate"}
    print(f"[9] 内置 policy 集合: {len(POLICIES)} 个")
    if POLICIES == expected:
        ok("6 policy 集合与预期一致")
    else:
        fail(f"期望 {expected}，实际 {POLICIES}")

    print()
    print(f"{GREEN}{passes} PASS{RESET} / {RED}{failures} FAIL{RESET}")

    if failures == 0:
        print(f"\n{GREEN}代码底盘自洽 — 所有核心证据成立。{RESET}")
    else:
        print(f"\n{RED}{failures} 项失败 — 代码有问题。{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
