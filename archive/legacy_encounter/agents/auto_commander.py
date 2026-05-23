from __future__ import annotations

import json
from typing import Any

from agents.command_interpreter import CommandInterpreter
from agents.llm_client import LLMError, OpenAICompatibleClient
from game.models import Battlefield, Order


SYSTEM_PROMPT = """
You are an autonomous tactical commander for a text tactical command game.

Every tick, inspect the battlefield and decide whether to intervene.
You are not the combat resolver. You only produce tactical orders.
The local rule engine decides combat results.

Output JSON only.

Allowed unit names:
- HG-01
- MG-249
- SMG-45
- RF-S
- ALL

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
- safe_cover

Output schema:
{
  "intervene": true,
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
- If the default deputy can handle the situation, set intervene=false and orders=[].
- Intervene when a high-value target appears, a unit is in danger, armor pressure rises, or a vague human policy would be useful.
- Do not invent kills or outcomes.
- JSON only.
""".strip()


class AutoCommander:
    def __init__(self) -> None:
        self.llm = OpenAICompatibleClient()

    def decide(self, bf: Battlefield) -> tuple[list[Order], str, str, bool]:
        if not self.llm.enabled:
            return [], bf.commander_policy, "AI commander offline；本 tick 交给默认副官。", False

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
                    "cover": u.cover,
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
                    "cover": e.cover,
                    "pressure": e.pressure,
                    "exposed": e.exposed,
                    "status": e.status,
                }
                for e in bf.enemy_units
            ],
            "global_status": bf.global_status,
            "recent_log": bf.log[-6:],
        }

        prompt = f"""
Battlefield context:
{json.dumps(context, ensure_ascii=False, indent=2)}

Decide whether to intervene this tick.
""".strip()

        try:
            data = self.llm.chat_json(SYSTEM_PROMPT, prompt)
        except LLMError as exc:
            return [], bf.commander_policy, f"AI commander fallback：{exc}", False

        if not self._clean_intervene(data.get("intervene")):
            return [], self._clean_policy(data.get("policy"), bf.commander_policy), str(data.get("commander_intent_summary") or "AI 判断无需介入。"), True

        orders = self._clean_orders(data.get("orders", []))
        policy = self._clean_policy(data.get("policy"), bf.commander_policy)
        summary = str(data.get("commander_intent_summary") or "AI commander 已介入。")
        return orders, policy, summary, True

    def _clean_orders(self, raw_orders: Any) -> list[Order]:
        if not isinstance(raw_orders, list):
            return []
        cleaner = CommandInterpreter()
        orders = []
        for item in raw_orders:
            if not isinstance(item, dict):
                continue
            unit = cleaner._clean_unit(item.get("unit"))
            action = cleaner._clean_action(item.get("action"))
            if not unit or not action:
                continue
            try:
                priority = int(item.get("priority") or 1)
            except (TypeError, ValueError):
                priority = 1
            orders.append(
                Order(
                    unit=unit,
                    action=action,
                    target=cleaner._clean_target(item.get("target")),
                    condition=cleaner._clean_condition(item.get("condition")),
                    constraints=cleaner._clean_constraints(item.get("constraints")),
                    priority=max(1, min(priority, 5)),
                )
            )
        return orders

    def _clean_policy(self, value: Any, fallback: str) -> str:
        return CommandInterpreter._clean_policy(CommandInterpreter(), value, fallback)

    def _clean_intervene(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "intervene")
        return bool(value)
