from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.auto_commander import AutoCommander
from agents.assistant_agent import TacticalAssistant
from agents.command_interpreter import CommandInterpreter
from game.models import Order
from game.rules import RuleEngine
from game.scenario import create_default_battlefield


@dataclass(frozen=True)
class DemoInput:
    kind: str
    command: str


HUMAN_SCRIPT_INPUTS = [
    DemoInput("普通指令", "MG 压制中路，RF 先打无人机，SMG 先别冲，HG 等破盾再处决"),
    DemoInput("模糊指令", "稳一点，别让中路崩，机会合适再动手"),
    DemoInput("危险指令", "所有人立刻冲出去贴脸打装甲，不要管掩体，也不要压制"),
    DemoInput("普通指令", "45 找安全窗口绕后，MG 继续压制装甲，RF 打暴露目标"),
    DemoInput("模糊指令", "现在别贪，能收就收，不能收就保人"),
    DemoInput("零指挥", ""),
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


def format_orders(orders: list[Order]) -> list[str]:
    if not orders:
        return ["direct_orders=[]"]
    lines = []
    for order in orders[:6]:
        target = f" target={order.target}" if order.target else ""
        condition = f" condition={order.condition}" if order.condition else ""
        constraints = f" constraints={order.constraints}" if order.constraints else ""
        lines.append(f"{order.unit}: {order.action}{target}{condition}{constraints} priority={order.priority}")
    return lines


def decision_label(mode: str, used_llm: bool) -> str:
    if mode == "zero-ai":
        return "Automation: local rules + default deputy, no LLM"
    if mode == "ai-interval":
        return f"Low-frequency AI: {'LLM intervention' if used_llm else 'no LLM this tick'}"
    return f"Command interpreter: {'LLM' if used_llm else 'fallback'}"


def render_frame(
    battlefield,
    mode: str,
    item: DemoInput,
    summary: str,
    used_llm: bool,
    player_orders: list[Order],
    tick_log: list[str],
) -> str:
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(f"[Tick {battlefield.tick - 1}->{battlefield.tick} resolved] Location: {battlefield.location} | Policy: {battlefield.commander_policy}")
    lines.append("-" * 72)
    lines.append(f"Mode: {mode}")
    lines.append(f"Input kind: {item.kind}")
    lines.append(f"Command: {item.command or '[zero-command / AI deputy]'}")
    lines.append(decision_label(mode, used_llm))
    lines.append(f"Parse: {summary}")
    lines.append("Orders:")
    for order_line in format_orders(player_orders):
        lines.append(f"  - {order_line}")

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


def run(interval: float, offline: bool, mode: str, limit: int | None, ai_every: int) -> None:
    if offline:
        import os

        os.environ["LLM_DISABLED"] = "1"

    battlefield = create_default_battlefield()
    auto_commander = AutoCommander()
    interpreter = CommandInterpreter()
    assistant = TacticalAssistant()
    rules = RuleEngine()
    resolved = False
    human_inputs = HUMAN_SCRIPT_INPUTS[:limit] if limit is not None else HUMAN_SCRIPT_INPUTS
    max_ticks = limit if limit is not None and mode in ("zero-ai", "ai-interval") else len(human_inputs)

    for index in range(max_ticks):
        if mode == "zero-ai":
            item = DemoInput("零 AI 自动战场", "[no human input; no LLM]")
            player_orders, policy, summary, used_llm = [], battlefield.commander_policy, "零 AI：本 tick 只运行本地自动战术。", False
        elif mode == "ai-interval":
            if index % ai_every == 0:
                item = DemoInput("低频 AI 介入", "[LLM reads battlefield at interval and may issue orders]")
                player_orders, policy, summary, used_llm = auto_commander.decide(battlefield)
            else:
                item = DemoInput("间隔等待", "[no LLM call this tick]")
                player_orders, policy, summary, used_llm = [], battlefield.commander_policy, "AI 介入间隔未到；本 tick 只运行本地自动战术。", False
        else:
            item = human_inputs[index]
            player_orders, policy, summary, used_llm = interpreter.interpret(item.command, battlefield)

        battlefield.commander_policy = policy
        deputy_orders = assistant.propose_orders(battlefield)
        for order in player_orders:
            order.priority += 10

        battlefield.log.append(f"[script] {summary}")
        tick_log = rules.resolve_tick(battlefield, deputy_orders + player_orders)
        battlefield.log.extend(tick_log)
        battlefield.tick += 1

        clear_screen()
        print(render_frame(battlefield, mode, item, summary, used_llm, player_orders, tick_log))
        sys.stdout.flush()
        time.sleep(interval)

        if battle_over(battlefield):
            resolved = True
            break

    clear_screen()
    final_item = DemoInput("final", "[final]")
    print(render_frame(battlefield, mode, final_item, "战斗结束。", False, [], []))
    if resolved:
        print("\n" + result_line(battlefield))
    else:
        if mode == "zero-ai":
            print("\n演示结束：零 AI 自动战场 tick 播放完毕，战斗仍在进行。")
        elif mode == "ai-interval":
            print("\n演示结束：低频 AI 介入 tick 播放完毕，战斗仍在进行。")
        else:
            print("\n演示结束：人类输入脚本播放完毕，战斗仍在进行。")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a real-time tactical demo.")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between ticks. Default: 5.0")
    parser.add_argument("--offline", action="store_true", help="Disable LLM and use local fallback/deputy behavior.")
    parser.add_argument(
        "--mode",
        choices=("zero-ai", "ai-interval", "human-script"),
        default="zero-ai",
        help="zero-ai is default local automation; ai-interval lets LLM intervene every N ticks; human-script feeds simulated human commands.",
    )
    parser.add_argument("--ai-every", type=int, default=4, help="In ai-interval mode, call LLM every N ticks. Default: 4")
    parser.add_argument("--limit", type=int, default=None, help="Limit ticks/inputs for quick checks.")
    args = parser.parse_args()
    run(args.interval, args.offline, args.mode, args.limit, max(1, args.ai_every))


if __name__ == "__main__":
    main()
