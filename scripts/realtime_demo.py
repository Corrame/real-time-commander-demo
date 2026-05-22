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
from game.display import render_state
from game.rules import RuleEngine
from game.scenario import create_default_battlefield


SCRIPTED_COMMANDS = [
    "MG 压制中路，RF 先打无人机，SMG 先别冲，HG 等破盾再处决",
    "",
    "45 等压制成功再绕后，沙鹰继续等破盾窗口",
    "全体稳一点，别追太深",
    "副官接管",
    "MG 继续压制装甲，RF 打暴露目标",
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


def run(interval: float) -> None:
    battlefield = create_default_battlefield()
    interpreter = CommandInterpreter()
    assistant = TacticalAssistant()
    rules = RuleEngine()

    for command in SCRIPTED_COMMANDS:
        clear_screen()
        print(render_state(battlefield))
        print(f"\nNext command: {command or '[zero-command / AI deputy]'}")
        sys.stdout.flush()
        time.sleep(interval)

        player_orders, policy, summary, used_llm = interpreter.interpret(command, battlefield)
        if used_llm:
            raise AssertionError("realtime demo must run without network LLM")

        battlefield.commander_policy = policy
        deputy_orders = assistant.propose_orders(battlefield)
        for order in player_orders:
            order.priority += 10

        battlefield.log.append(f"[script] {summary}")
        battlefield.log.extend(rules.resolve_tick(battlefield, deputy_orders + player_orders))
        battlefield.tick += 1

        if battle_over(battlefield):
            break

    clear_screen()
    print(render_state(battlefield))
    print("\n" + result_line(battlefield))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local real-time scripted combat demo.")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between ticks. Default: 1.0")
    args = parser.parse_args()
    run(args.interval)


if __name__ == "__main__":
    main()
