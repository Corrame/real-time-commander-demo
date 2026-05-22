from __future__ import annotations

from agents.assistant_agent import TacticalAssistant
from agents.command_interpreter import CommandInterpreter
from game.display import render_state
from game.rules import RuleEngine
from game.scenario import create_default_battlefield


class GameMaster:
    def __init__(self) -> None:
        self.bf = create_default_battlefield()
        self.interpreter = CommandInterpreter()
        self.assistant = TacticalAssistant()
        self.rules = RuleEngine()

    def run(self) -> None:
        print("\nReal-Time Commander Demo")
        print("输入自然语言命令；直接回车 = 零指挥，由 AI 副官/默认战术接管。")
        print("输入 quit 退出。\n")

        while True:
            print(render_state(self.bf))

            if self._battle_over():
                self._print_result()
                break

            command = input("Commander > ").strip()
            if command.lower() in ("quit", "exit", "q"):
                print("撤出模拟。")
                break

            player_orders, policy, summary, used_llm = self.interpreter.interpret(command, self.bf)
            self.bf.commander_policy = policy

            deputy_orders = self.assistant.propose_orders(self.bf)

            # Player orders have higher priority than deputy suggestions.
            for o in player_orders:
                o.priority += 10

            orders = deputy_orders + player_orders

            self.bf.log.append(f"[命令解析] {summary} ({'LLM' if used_llm else 'fallback/zero-command'})")
            if not player_orders:
                self.bf.log.append("[AI副官] 本 tick 按默认战术维持调度。")
            else:
                self.bf.log.append("[AI副官] 已将玩家命令叠加为高优先级战术约束。")

            tick_log = self.rules.resolve_tick(self.bf, orders)
            self.bf.log.extend(tick_log)
            self.bf.tick += 1

    def _battle_over(self) -> bool:
        friend_down = sum(1 for u in self.bf.friendly_units if not u.is_alive())
        armor_alive = any(e.kind == "armored" and e.is_alive() for e in self.bf.enemy_units)
        enemy_alive = any(e.is_alive() for e in self.bf.enemy_units)

        if friend_down >= 2:
            return True
        if not enemy_alive:
            return True
        if not armor_alive:
            return True
        if self.bf.tick > self.bf.max_tick:
            return True
        if "enemy_at_core_edge" in self.bf.global_status and self.bf.tick > 10:
            return True
        return False

    def _print_result(self) -> None:
        print("\n" + "=" * 72)
        friend_down = sum(1 for u in self.bf.friendly_units if not u.is_alive())
        armor_alive = any(e.kind == "armored" and e.is_alive() for e in self.bf.enemy_units)
        enemy_alive = any(e.is_alive() for e in self.bf.enemy_units)

        if friend_down >= 2:
            print("结果：失败。两名以上友方单位失去战斗能力。")
        elif not enemy_alive:
            print("结果：胜利。敌方单位被清除。")
        elif not armor_alive:
            print("结果：胜利。敌方装甲单位被清除，阵地压力解除。")
        elif self.bf.tick > self.bf.max_tick:
            print("结果：胜利。小队坚持到预定时间并守住阵地。")
        else:
            print("结果：失败。敌人逼近核心区域。")
        print("=" * 72)
