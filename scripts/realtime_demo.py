from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["LLM_DISABLED"] = "1"

from agents.assistant_agent import TacticalAssistant
from agents.command_interpreter import CommandInterpreter
from game.rules import RuleEngine
from game.scenario import create_default_battlefield


SCRIPTED_COMMANDS = [
    "全体稳一点，MG 压制中路，RF 先打无人机，SMG 先别冲，HG 等破盾再处决",
    "",
    "45 等压制成功再绕后，沙鹰继续等破盾窗口",
    "MG 继续压制装甲，RF 打暴露目标",
    "全体别追太深，保持阵线",
    "45 找窗口绕后，HG 授权处决装甲",
    "",
]


def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def battle_over(battlefield) -> bool:
    friend_down = sum(1 for unit in battlefield.friendly_units if not unit.is_alive())
    armor_alive = any(enemy.kind == "armored" and enemy.is_alive() for enemy in battlefield.enemy_units)
    enemy_alive = any(enemy.is_alive() for enemy in battlefield.enemy_units)

    return (
        friend_down >= 2
        or not enemy_alive
        or not armor_alive
        or battlefield.tick > battlefield.max_tick
        or ("enemy_at_core_edge" in battlefield.global_status and battlefield.tick > 10)
    )


def result_line(battlefield) -> str:
    friend_down = sum(1 for unit in battlefield.friendly_units if not unit.is_alive())
    armor_alive = any(enemy.kind == "armored" and enemy.is_alive() for enemy in battlefield.enemy_units)
    enemy_alive = any(enemy.is_alive() for enemy in battlefield.enemy_units)

    if friend_down >= 2:
        return "结果：失败。两名以上友方单位失去战斗能力。"
    if not enemy_alive:
        return "结果：胜利。敌方单位被清除。"
    if not armor_alive:
        return "结果：胜利。敌方装甲单位被清除。"
    if battlefield.tick > battlefield.max_tick:
        return "结果：胜利。小队坚持到预定时间。"
    return "结果：失败。敌人逼近核心区域。"


def render_frame(battlefield, command: str, summary: str, tick_log: list[str]) -> str:
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(f"[Tick {battlefield.tick - 1}->{battlefield.tick} resolved] Location: {battlefield.location} | Policy: {battlefield.commander_policy}")
    lines.append("-" * 72)
    lines.append(f"Command: {command or '[zero-command / AI deputy]'}")
    lines.append(f"Parse: {summary}")

    lines.append("")
    lines.append("Friendly:")
    for unit in battlefield.friendly_units:
        dead = " [DOWN]" if not unit.is_alive() else ""
        lines.append(f"  - {unit.short()}{dead}")

    lines.append("")
    lines.append("Enemy:")
    for enemy in battlefield.enemy_units:
        dead = " [DOWN]" if not enemy.is_alive() else ""
        lines.append(f"  - {enemy.short()}{dead}")

    friendly_logs = [item for item in tick_log if item.startswith(("HG-01", "MG-249", "SMG-45", "RF-S"))]
    enemy_logs = [item for item in tick_log if item not in friendly_logs]

    lines.append("")
    lines.append("This tick - squad:")
    for item in friendly_logs[:8] or ["无直接我方动作。"]:
        lines.append(f"  * {item}")

    lines.append("")
    lines.append("This tick - enemy:")
    hits = sum("命中" in item for item in enemy_logs)
    misses = sum("偏出" in item for item in enemy_logs)
    pinned = sum("推进失败" in item for item in enemy_logs)
    pressure = sum("核心区域" in item for item in enemy_logs)
    lines.append(f"  * hits={hits} misses={misses} pinned={pinned} core_pressure={pressure}")
    for item in enemy_logs[:4]:
        lines.append(f"  * {item}")

    lines.append("=" * 72)
    return "\n".join(lines)


def run(interval: float) -> None:
    battlefield = create_default_battlefield()
    interpreter = CommandInterpreter()
    assistant = TacticalAssistant()
    rules = RuleEngine()
    resolved = False

    for command in SCRIPTED_COMMANDS:
        player_orders, policy, summary, used_llm = interpreter.interpret(command, battlefield)
        if used_llm:
            raise AssertionError("realtime demo must run without network LLM")

        battlefield.commander_policy = policy
        deputy_orders = assistant.propose_orders(battlefield)
        for order in player_orders:
            order.priority += 10

        battlefield.log.append(f"[script] {summary}")
        tick_log = rules.resolve_tick(battlefield, deputy_orders + player_orders)
        battlefield.log.extend(tick_log)
        battlefield.tick += 1

        clear_screen()
        print(render_frame(battlefield, command, summary, tick_log))
        sys.stdout.flush()
        time.sleep(interval)

        if battle_over(battlefield):
            resolved = True
            break

    clear_screen()
    print(render_frame(battlefield, "[final]", "战斗结束。", []))
    if resolved:
        print("\n" + result_line(battlefield))
    else:
        print("\n演示结束：脚本指令播放完毕，战斗仍在进行。")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local real-time scripted combat demo.")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between ticks. Default: 5.0")
    args = parser.parse_args()
    run(args.interval)


if __name__ == "__main__":
    main()
