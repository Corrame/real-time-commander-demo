from __future__ import annotations

import json
import re
from typing import Any

from agents.llm_client import OpenAICompatibleClient, LLMError
from game.models import Battlefield, Order


SYSTEM_PROMPT = """
You are the Command Interpreter for a text tactical command game.

Your job:
- Convert the commander's natural-language intent into structured JSON orders.
- You do NOT decide combat results.
- You do NOT invent victory.
- You output JSON only.

Allowed unit names:
- HG-01: handgun finisher, bold, waits for execution windows.
- MG-249: machine gun suppressor, suppresses middle lane and breaks shields.
- SMG-45: veteran flanker, can hold, flank, ambush, retreat.
- RF-S: cautious rifle marksman, anti-drone, precision target removal.

Allowed actions:
- hold
- advance
- suppress
- flank
- retreat
- focus_fire
- prioritize_target
- execute
- free_fire
- do_not_chase
- set_policy
- authorize
- deny

Targets may include:
- middle_lane
- left_flank
- right_flank
- drone
- armored
- infantry
- exposed_enemy
- core_area

Output schema:
{
  "orders": [
    {
      "unit": "MG-249",
      "action": "suppress",
      "target": "middle_lane",
      "condition": null,
      "constraints": ["do_not_advance"],
      "priority": 2
    }
  ],
  "policy": "balanced|conservative|aggressive|hold_position|preserve_hp|rapid_clear",
  "commander_intent_summary": "short Chinese summary"
}

Rules:
- If player input is empty, output no direct orders and policy balanced.
- Preserve conditions such as "after shield breaks", "don't chase", "wait for suppression".
- If the user asks a unit not to rush, use hold with constraints.
- If the user asks "AI 接管" or "副官接管", output no direct orders and policy balanced or conservative.
- JSON only.
""".strip()


class CommandInterpreter:
    def __init__(self) -> None:
        self.llm = OpenAICompatibleClient()

    def interpret(self, command: str, bf: Battlefield) -> tuple[list[Order], str, str, bool]:
        """
        Returns: orders, policy, summary, used_llm
        """
        command = command.strip()
        if not command:
            return [], bf.commander_policy, "本 tick 零指挥，由 AI 副官/默认战术接管。", False

        if self.llm.enabled:
            try:
                result = self._interpret_with_llm(command, bf)
                return result[0], result[1], result[2], True
            except LLMError as exc:
                print(f"[LLM fallback] {exc}")

        orders, policy, summary = self._fallback_interpret(command, bf)
        return orders, policy, summary, False

    def _interpret_with_llm(self, command: str, bf: Battlefield) -> tuple[list[Order], str, str]:
        context = {
            "tick": bf.tick,
            "policy": bf.commander_policy,
            "friendlies": [
                {
                    "name": u.name,
                    "weapon_type": u.weapon_type,
                    "hp": u.hp,
                    "ammo": u.ammo,
                    "position": u.position,
                    "status": u.status,
                    "personality": u.personality,
                    "role": u.role,
                }
                for u in bf.friendly_units
            ],
            "enemies": [
                {
                    "name": e.name,
                    "kind": e.kind,
                    "hp": e.hp,
                    "shield": e.shield,
                    "position": e.position,
                    "pressure": e.pressure,
                    "exposed": e.exposed,
                    "status": e.status,
                }
                for e in bf.enemy_units
            ],
            "global_status": bf.global_status,
        }

        user_prompt = f"""
Battlefield context:
{json.dumps(context, ensure_ascii=False, indent=2)}

Commander command:
{command}
""".strip()

        data = self.llm.chat_json(SYSTEM_PROMPT, user_prompt)
        policy = str(data.get("policy") or bf.commander_policy or "balanced")
        summary = str(data.get("commander_intent_summary") or "命令已解析。")
        orders = []
        for item in data.get("orders", []):
            if not isinstance(item, dict):
                continue
            orders.append(
                Order(
                    unit=str(item.get("unit") or "ALL"),
                    action=str(item.get("action") or "hold"),
                    target=item.get("target"),
                    condition=item.get("condition"),
                    constraints=list(item.get("constraints") or []),
                    priority=int(item.get("priority") or 1),
                    raw_text=command,
                )
            )
        return orders, policy, summary

    def _fallback_interpret(self, command: str, bf: Battlefield) -> tuple[list[Order], str, str]:
        """
        Emergency fallback, not the core experience.
        It keeps the demo runnable when no LLM endpoint exists.
        """
        text = command.lower()
        orders: list[Order] = []
        policy = bf.commander_policy

        def add(unit: str, action: str, target: str | None = None, condition: str | None = None, constraints: list[str] | None = None, priority: int = 1) -> None:
            orders.append(Order(unit=unit, action=action, target=target, condition=condition, constraints=constraints or [], priority=priority, raw_text=command))

        if any(k in text for k in ["保守", "稳", "别冒险", "优先保命"]):
            policy = "conservative"
        if any(k in text for k in ["激进", "速攻", "快清", "rush"]):
            policy = "aggressive"
        if any(k in text for k in ["ai接管", "副官接管", "自动"]):
            return [], policy, "副官接管，本 tick 无直接命令。"

        # Unit aliases
        mg = any(k in text for k in ["mg", "m249", "机枪", "mg-249"])
        smg = any(k in text for k in ["smg", "45", "冲锋", "smg-45"])
        hg = any(k in text for k in ["hg", "沙鹰", "手枪", "处决", "hg-01"])
        rf = any(k in text for k in ["rf", "春田", "狙", "步枪", "rf-s"])

        if mg or "压制" in text:
            if "压制" in text or mg:
                add("MG-249", "suppress", "middle_lane", constraints=["do_not_advance"], priority=2)

        if rf or "无人机" in text:
            if "无人机" in text or "drone" in text:
                add("RF-S", "prioritize_target", "drone", priority=3)
            elif rf:
                add("RF-S", "focus_fire", "exposed_enemy", priority=2)

        if smg:
            if any(k in text for k in ["别冲", "不要急", "先别", "等"]):
                add("SMG-45", "hold", "left_flank", constraints=["stay_hidden", "do_not_chase"], priority=3)
            elif any(k in text for k in ["绕", "侧", "flank"]):
                add("SMG-45", "flank", "left_flank", priority=2)

        if hg or "破盾" in text:
            if "破盾" in text or "处决" in text:
                add("HG-01", "execute", "armored", condition="enemy_shield_broken", constraints=["do_not_expose_before_condition"], priority=3)
            elif hg:
                add("HG-01", "hold", constraints=["wait_execution_window"], priority=2)

        if "撤" in text or "retreat" in text:
            add("ALL", "retreat", "safe_cover", priority=5)
        if "别追" in text or "不要追" in text:
            add("ALL", "do_not_chase", priority=4)

        summary = "fallback 解析：已将命令转换为结构化 orders。"
        return orders, policy, summary
