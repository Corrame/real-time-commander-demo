from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["LLM_DISABLED"] = "1"

from agents.assistant_agent import TacticalAssistant
from agents.command_interpreter import CommandInterpreter
from game.rules import RuleEngine
from game.scenario import create_default_battlefield


def run_scripted_demo() -> None:
    battlefield = create_default_battlefield()
    interpreter = CommandInterpreter()
    assistant = TacticalAssistant()
    rules = RuleEngine()

    commands = [
        "MG 压制中路，RF 先打无人机，SMG 先别冲，HG 等破盾再处决",
        "",
        "45 等压制成功再绕后，沙鹰继续等破盾窗口",
        "全体稳一点，别追太深",
        "副官接管",
    ]

    for command in commands:
        player_orders, policy, summary, used_llm = interpreter.interpret(command, battlefield)
        if used_llm:
            raise AssertionError("smoke demo must run without network LLM")

        battlefield.commander_policy = policy
        deputy_orders = assistant.propose_orders(battlefield)
        for order in player_orders:
            order.priority += 10

        log = rules.resolve_tick(battlefield, deputy_orders + player_orders)
        battlefield.log.append(f"[smoke] {summary}")
        battlefield.log.extend(log)
        battlefield.tick += 1

    living_friendlies = len(battlefield.living_friendlies())
    living_enemies = len(battlefield.living_enemies())
    if living_friendlies < 3:
        raise AssertionError(f"too many friendlies down: {living_friendlies}")
    if living_enemies >= 7:
        raise AssertionError("scripted commands did not affect the enemy state")
    if not any("压制" in item or "处决" in item or "绕" in item for item in battlefield.log):
        raise AssertionError("expected tactical action logs were not produced")

    print(f"smoke ok: tick={battlefield.tick} friendlies={living_friendlies} enemies={living_enemies}")


if __name__ == "__main__":
    run_scripted_demo()
