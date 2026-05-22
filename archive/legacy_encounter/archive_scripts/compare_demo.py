"""
compare_demo.py  —  Side-by-side comparison: B = no command (squad stays "dumb",
stalemate)  vs  A = correctly commanded (squad "wakes up", breaks the deadlock).

Usage:
    python scripts/compare_demo.py [--seed 42] [--limit N] [--offline]

Design intent:
- The default battlefield is a deliberately neutral 50/50 canvas (two squads of
  fools trading fire).  A player command = turning OUR fools into non-fools.
- B-line = no command = squad stays dumb = stalemate.
- A-line = correct command, parsed by a REAL LLM into valid tactics = squad
  wakes up = breaks the deadlock and gains a visible edge.

Constraints honoured:
1. Fixed random seed   — both timelines use RuleEngine(seed=<same>).
2. Identical start     — both battlefields are deepcopy of create_default_battlefield().
3. Single variable     — A-line gets player commands (LLM-parsed); B-line gets none.
4. Engine is read-only — game/rules.py, command_interpreter.py, llm_client.py untouched.

Note on commands: A-line uses COMMAND_SCRIPT below, NOT realtime_demo's
HUMAN_SCRIPT_INPUTS.  The latter mixes in deliberately vague/dangerous lines
(for a different teaching point); this two-way demo only shows "no command vs
CORRECT command", so we feed clear, tactically-sound instructions instead.
"""
from __future__ import annotations

import argparse
import copy
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.assistant_agent import TacticalAssistant
from agents.command_interpreter import CommandInterpreter
from game.models import Battlefield, Order
from game.rules import RuleEngine
from game.scenario import create_default_battlefield
from scripts.realtime_demo import battle_over, result_line


# A-line script: clear, tactically-correct natural-language commands.
# Each line expresses unambiguous intent the LLM can translate into valid orders.
COMMAND_SCRIPT = [
    "MG-249 全力压制中路装甲，RF-S 优先狙杀侦察无人机，SMG-45 在左翼隐蔽待机不要暴露，HG-01 等装甲破盾后再处决",
    "MG-249 继续压制中路保持装甲破盾，RF-S 集火已暴露的中路装甲，HG-01 抓住破盾窗口处决装甲",
    "RF-S 集火剩余装甲，MG-249 压制掩护，HG-01 处决任何破盾的装甲目标",
    "SMG-45 现在从左翼绕后切入打暴露的步兵，RF-S 继续清剩余装甲，MG-249 压制中路",
    "全员集火清剿剩余敌人，RF-S 优先点掉残血目标，HG-01 处决一切破盾装甲",
    "收尾，清掉最后的敌人，注意保人不要无谓暴露",
]


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------

@dataclass
class TickSnapshot:
    tick: int
    friendly_hp: dict[str, int]
    enemy_hp: dict[str, int]
    enemy_shield: dict[str, int]
    tick_log: list[str]
    command: str
    parsed_orders: list[str]
    used_llm: bool
    summary: str


def snap(
    bf: Battlefield,
    tick_log: list[str],
    command: str,
    parsed_orders: list[str],
    used_llm: bool,
    summary: str,
) -> TickSnapshot:
    return TickSnapshot(
        tick=bf.tick,
        friendly_hp={u.name: u.hp for u in bf.friendly_units},
        enemy_hp={e.name: e.hp for e in bf.enemy_units},
        enemy_shield={e.name: e.shield for e in bf.enemy_units},
        tick_log=list(tick_log),
        command=command,
        parsed_orders=parsed_orders,
        used_llm=used_llm,
        summary=summary,
    )


def order_repr(o: Order) -> str:
    target = f" target={o.target}" if o.target else ""
    cond = f" cond={o.condition}" if o.condition else ""
    constr = f" constr={o.constraints}" if o.constraints else ""
    return f"{o.unit}:{o.action}{target}{cond}{constr} prio={o.priority}"


# ---------------------------------------------------------------------------
# Single-timeline runner
# ---------------------------------------------------------------------------

def run_timeline(
    label: str,
    seed: int,
    has_command: bool,
    limit: int | None,
) -> tuple[list[TickSnapshot], Battlefield]:
    """Run one timeline.  Returns (snapshots, final_battlefield)."""
    bf: Battlefield = copy.deepcopy(create_default_battlefield())
    rules = RuleEngine(seed=seed)
    interpreter = CommandInterpreter()
    assistant = TacticalAssistant()

    commands = COMMAND_SCRIPT[:limit] if limit is not None else COMMAND_SCRIPT
    max_ticks = len(commands)

    snapshots: list[TickSnapshot] = []

    for index in range(max_ticks):
        if has_command:
            command_text = commands[index]
            player_orders, policy, summary, used_llm = interpreter.interpret(command_text, bf)
        else:
            # B-line: no player command, zero-ai deputy only
            command_text = "[zero-command]"
            player_orders, policy, summary, used_llm = [], bf.commander_policy, "零 AI：本 tick 只运行本地自动战术。", False

        bf.commander_policy = policy
        deputy_orders = assistant.propose_orders(bf)
        for order in player_orders:
            order.priority += 10  # player commands take precedence over deputy

        parsed = [order_repr(o) for o in player_orders]

        bf.log.append(f"[script] {summary}")
        tick_log = rules.resolve_tick(bf, deputy_orders + player_orders)
        bf.log.extend(tick_log)

        snapshots.append(snap(bf, tick_log, command_text, parsed, used_llm, summary))

        bf.tick += 1

        if battle_over(bf):
            break

    return snapshots, bf


# ---------------------------------------------------------------------------
# Side-by-side rendering
# ---------------------------------------------------------------------------

DIVIDER = "=" * 76
HALF = "-" * 38


def unit_status_line(bf: Battlefield, name: str) -> str:
    unit = next((u for u in bf.friendly_units if u.name == name), None)
    if unit is None:
        return f"{name}: N/A"
    tag = "[DOWN]" if not unit.is_alive() else ""
    return f"{name} HP={unit.hp:3d} Ammo={unit.ammo:2d} Cover={unit.cover:2d} {tag}"


def enemy_status_line(bf: Battlefield, name: str) -> str:
    e = next((en for en in bf.enemy_units if en.name == name), None)
    if e is None:
        return f"{name}: N/A"
    tag = "[DOWN]" if not e.is_alive() else ""
    return f"HP={e.hp:3d} Shield={e.shield:2d} Pressure={e.pressure:2d} {tag}"


def render_side_by_side(
    snap_a: TickSnapshot,
    snap_b: TickSnapshot,
    bf_a: Battlefield,
    bf_b: Battlefield,
) -> str:
    lines: list[str] = []
    tick = snap_a.tick
    lines.append(DIVIDER)
    lines.append(f"  Tick {tick}  |  A: WITH command  ||  B: WITHOUT command")
    lines.append(DIVIDER)

    # Commands + how the LLM parsed them (proves "command -> valid tactics").
    cmd_a = (snap_a.command or "[zero]")[:70]
    parse_tag = "LLM" if snap_a.used_llm else "fallback"
    lines.append(f"  A cmd : {cmd_a}")
    lines.append(f"  A parse ({parse_tag}): {snap_a.summary}")
    if snap_a.parsed_orders:
        for po in snap_a.parsed_orders:
            lines.append(f"      -> {po}")
    else:
        lines.append("      -> (no direct orders)")
    lines.append(f"  B cmd : [zero-command]  (squad runs default deputy only)")
    lines.append("")

    # Friendly HP
    lines.append("  Friendly HP:")
    for uname in ["HG-01", "MG-249", "SMG-45", "RF-S"]:
        hp_a = snap_a.friendly_hp.get(uname, "?")
        hp_b = snap_b.friendly_hp.get(uname, "?")
        diff = ""
        if isinstance(hp_a, int) and isinstance(hp_b, int):
            d = hp_a - hp_b
            diff = f"  [Δ {d:+d}]" if d != 0 else ""
        lines.append(f"    {uname:<10s}  A={hp_a:>3}  B={hp_b:>3}{diff}")

    lines.append("")
    lines.append("  Enemy HP / Shield:")
    for ename, bf_a_ref, bf_b_ref in [
        ("Armored Assault 1", bf_a, bf_b),
        ("Armored Assault 2", bf_a, bf_b),
        ("Scout Drone", bf_a, bf_b),
    ]:
        hp_a = snap_a.enemy_hp.get(ename, "?")
        hp_b = snap_b.enemy_hp.get(ename, "?")
        sh_a = snap_a.enemy_shield.get(ename, "?")
        sh_b = snap_b.enemy_shield.get(ename, "?")
        hp_diff = ""
        if isinstance(hp_a, int) and isinstance(hp_b, int):
            d = hp_b - hp_a  # positive = B enemy is healthier (A did more damage)
            hp_diff = f"  [A dealt Δ{d:+d}]" if d != 0 else ""
        lines.append(f"    {ename:<22s}  A hp={hp_a:>3} sh={sh_a:>2}  B hp={hp_b:>3} sh={sh_b:>2}{hp_diff}")

    lines.append("")
    lines.append("  A tick log (squad):")
    for entry in [e for e in snap_a.tick_log if any(e.startswith(n) for n in ["HG", "MG", "SMG", "RF"])][:4]:
        lines.append(f"    * {entry}")

    lines.append("  B tick log (squad):")
    for entry in [e for e in snap_b.tick_log if any(e.startswith(n) for n in ["HG", "MG", "SMG", "RF"])][:4]:
        lines.append(f"    * {entry}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Final comparison summary
# ---------------------------------------------------------------------------

def compute_summary(bf: Battlefield) -> dict:
    friendly_alive = sum(1 for u in bf.friendly_units if u.is_alive())
    friendly_total_hp = sum(u.hp for u in bf.friendly_units)
    enemy_alive = sum(1 for e in bf.enemy_units if e.is_alive())
    enemy_total_hp = sum(e.hp for e in bf.enemy_units)
    ticks_used = bf.tick - 1
    return {
        "friendly_alive": friendly_alive,
        "friendly_total_hp": friendly_total_hp,
        "enemy_alive": enemy_alive,
        "enemy_total_hp": enemy_total_hp,
        "ticks_used": ticks_used,
    }


def render_final_comparison(bf_a: Battlefield, bf_b: Battlefield) -> str:
    sa = compute_summary(bf_a)
    sb = compute_summary(bf_b)
    lines: list[str] = []
    lines.append(DIVIDER)
    lines.append("  FINAL COMPARISON")
    lines.append(DIVIDER)
    lines.append(f"  {'Metric':<28s}  {'A (with cmd)':>14}  {'B (zero-cmd)':>14}  {'Δ (A-B)':>8}")
    lines.append("  " + "-" * 70)

    for key, label in [
        ("friendly_alive", "Friendly alive"),
        ("friendly_total_hp", "Friendly total HP"),
        ("enemy_alive", "Enemy alive"),
        ("enemy_total_hp", "Enemy total HP"),
        ("ticks_used", "Ticks used"),
    ]:
        va = sa[key]
        vb = sb[key]
        diff = va - vb
        diff_str = f"{diff:+d}" if diff != 0 else "same"
        lines.append(f"  {label:<28s}  {va:>14}  {vb:>14}  {diff_str:>8}")

    lines.append("")
    lines.append(f"  A result: {result_line(bf_a)}")
    lines.append(f"  B result: {result_line(bf_b)}")
    lines.append(DIVIDER)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import os

    parser = argparse.ArgumentParser(
        description="Side-by-side compare: A=correctly commanded (real LLM) vs B=zero-ai."
    )
    parser.add_argument("--seed", type=int, default=42, help="Fixed RNG seed for both timelines. Default: 42")
    parser.add_argument("--limit", type=int, default=None, help="Limit ticks/inputs. Default: all (6 inputs).")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Force LLM off and use local fallback parsing (debug only; not the intended demo).",
    )
    args = parser.parse_args()

    if args.offline:
        os.environ["LLM_DISABLED"] = "1"
    else:
        # A-line must use the real LLM path. Verify it is configured before running;
        # do not silently fall back, that defeats the point of this demo.
        probe = CommandInterpreter()
        if not probe.llm.enabled:
            print(DIVIDER)
            print("  LLM 不可用，无法演示『命令被正确解析』。请检查：")
            print("    - openai 包是否安装 (pip install openai)")
            print("    - DEEPSEEK_API_KEY 或 LLM_API_KEY 是否在环境变量或 .env 中")
            print(f"    - 当前: base_url={probe.llm.base_url} model={probe.llm.model}")
            print(f"            api_key_present={bool(probe.llm.api_key)} disabled={probe.llm.disabled}")
            print("  或加 --offline 走本地 fallback（仅供调试，非本演示目标）。")
            print(DIVIDER)
            sys.exit(1)

    seed = args.seed
    limit = args.limit

    mode_tag = "fallback(offline)" if args.offline else "real LLM"
    print(DIVIDER)
    print(f"  COMPARE DEMO  seed={seed}  |  A=correct command ({mode_tag})  ||  B=zero-ai")
    print(DIVIDER)
    print("  Running A-timeline (correctly commanded)...")
    snaps_a, bf_a = run_timeline("A", seed=seed, has_command=True, limit=limit)

    print("  Running B-timeline (zero-ai, no player commands)...")
    snaps_b, bf_b = run_timeline("B", seed=seed, has_command=False, limit=limit)

    # Align tick count for display (zip on shorter)
    for snap_a, snap_b in zip(snaps_a, snaps_b):
        print(render_side_by_side(snap_a, snap_b, bf_a, bf_b))

    print(render_final_comparison(bf_a, bf_b))


if __name__ == "__main__":
    main()
