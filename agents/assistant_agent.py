from __future__ import annotations

from game.models import Battlefield, Order


class TacticalAssistant:
    """
    Default AI deputy.
    This is intentionally rules-based for MVP:
    - Low token cost
    - Stable behavior
    - Player can override with natural language
    """

    def propose_orders(self, bf: Battlefield) -> list[Order]:
        orders: list[Order] = []
        alive_enemies = bf.living_enemies()
        if not alive_enemies:
            return orders

        drone_alive = any(e.kind == "drone" and e.is_alive() for e in alive_enemies)
        armored_alive = any(e.kind == "armored" and e.is_alive() for e in alive_enemies)
        armor_shield_up = any(e.kind == "armored" and e.is_alive() and e.shield > 0 for e in alive_enemies)

        # Baseline: maintain system even with zero command.
        if armored_alive:
            orders.append(Order(unit="MG-249", action="suppress", target="middle_lane", constraints=["do_not_advance"], priority=1))
        if drone_alive:
            orders.append(Order(unit="RF-S", action="prioritize_target", target="drone", priority=1))
        if armor_shield_up:
            orders.append(Order(unit="HG-01", action="execute", target="armored", condition="enemy_shield_broken", constraints=["do_not_expose_before_condition"], priority=1))
            orders.append(Order(unit="SMG-45", action="hold", target="left_flank", constraints=["stay_hidden"], priority=1))
        else:
            orders.append(Order(unit="SMG-45", action="flank", target="left_flank", priority=1))
            orders.append(Order(unit="HG-01", action="execute", target="armored", condition="enemy_shield_broken", priority=1))

        if bf.commander_policy in ("conservative", "preserve_hp", "hold_position"):
            orders.append(Order(unit="ALL", action="do_not_chase", priority=2))
        elif bf.commander_policy in ("aggressive", "rapid_clear"):
            orders.append(Order(unit="SMG-45", action="flank", target="left_flank", priority=2))
            orders.append(Order(unit="MG-249", action="suppress", target="middle_lane", priority=2))

        return orders
