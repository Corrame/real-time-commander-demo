from __future__ import annotations

import random
from collections import defaultdict

from game.models import Battlefield, Unit, Enemy, Order


class RuleEngine:
    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)

    def resolve_tick(self, bf: Battlefield, orders: list[Order]) -> list[str]:
        log: list[str] = []
        if not bf.living_friendlies() or not bf.living_enemies():
            return log

        normalized = self._normalize_orders(orders)
        by_unit: dict[str, list[Order]] = defaultdict(list)
        global_orders: list[Order] = []

        for o in normalized:
            if o.unit.upper() == "ALL":
                global_orders.append(o)
            else:
                by_unit[o.unit].append(o)

        for unit in bf.living_friendlies():
            unit_orders = list(global_orders) + by_unit.get(unit.name, [])
            unit_orders = sorted(unit_orders, key=lambda o: o.priority, reverse=True)
            if not unit_orders:
                unit_orders = [self._default_order_for(unit, bf)]

            unit_log = self._act_unit(unit, bf, unit_orders)
            log.extend(unit_log)

        log.extend(self._enemy_phase(bf))
        self._cleanup_status(bf)
        return log

    def _normalize_orders(self, orders: list[Order]) -> list[Order]:
        out = []
        aliases = {
            "hg": "HG-01",
            "hg-01": "HG-01",
            "HG-01": "HG-01",
            "mg": "MG-249",
            "mg-249": "MG-249",
            "MG-249": "MG-249",
            "smg": "SMG-45",
            "smg-45": "SMG-45",
            "SMG-45": "SMG-45",
            "rf": "RF-S",
            "rf-s": "RF-S",
            "RF-S": "RF-S",
            "ALL": "ALL",
            "all": "ALL",
        }
        allowed_actions = {
            "hold", "advance", "suppress", "flank", "retreat", "focus_fire",
            "prioritize_target", "execute", "free_fire", "do_not_chase",
            "set_policy", "authorize", "deny",
        }
        for o in orders:
            unit = aliases.get(o.unit, o.unit)
            action = o.action if o.action in allowed_actions else "hold"
            out.append(Order(unit=unit, action=action, target=o.target, condition=o.condition, constraints=o.constraints, priority=o.priority, raw_text=o.raw_text))
        return out

    def _default_order_for(self, unit: Unit, bf: Battlefield) -> Order:
        if unit.weapon_type == "MG":
            return Order(unit=unit.name, action="suppress", target="middle_lane")
        if unit.weapon_type == "RF":
            return Order(unit=unit.name, action="prioritize_target", target="drone")
        if unit.weapon_type == "SMG":
            return Order(unit=unit.name, action="hold", target="left_flank", constraints=["stay_hidden"])
        if unit.weapon_type == "HG":
            return Order(unit=unit.name, action="execute", target="armored", condition="enemy_shield_broken")
        return Order(unit=unit.name, action="hold")

    def _act_unit(self, unit: Unit, bf: Battlefield, orders: list[Order]) -> list[str]:
        log: list[str] = []
        primary = orders[0]
        personality_note = self._personality_note(unit)

        # Apply global constraints first.
        for o in orders:
            if o.action == "do_not_chase":
                self._add_status(unit, "do_not_chase")
                log.append(f"{unit.name} 接收到禁止追击约束，行动边界收紧。")

        if primary.action == "do_not_chase":
            unit.cover = min(86, unit.cover + 4)
            self._add_status(unit, "holding")
            log.append(f"{unit.name} 将禁止追击作为主约束，收住阵位并等待下一窗口。{personality_note}")
            return log

        if primary.action == "set_policy":
            log.append(f"{unit.name} 接收到全局方针调整，维持当前战术职责并等待副官重排。")
            return log

        if primary.action == "authorize":
            self._add_status(unit, "authorized")
            log.append(f"{unit.name} 获得授权，会在职责窗口内主动抓机会。")
            return log

        if primary.action == "deny":
            self._add_status(unit, "denied")
            unit.cover = min(90, unit.cover + 5)
            log.append(f"{unit.name} 收到否决，取消高风险动作并回收暴露。")
            return log

        if primary.action == "hold":
            self._add_status(unit, "holding")
            if "stay_hidden" in primary.constraints:
                self._add_status(unit, "hidden")
                cover_gain = 8 if unit.personality in ("cautious", "veteran") else 5
                unit.cover = min(88, unit.cover + cover_gain)
                log.append(f"{unit.name} 保持隐蔽等待，掩体利用提升。{personality_note}")
            else:
                cover_gain = 5 if unit.personality == "cautious" else 3
                unit.cover = min(82, unit.cover + cover_gain)
                log.append(f"{unit.name} 守住当前位置，等待更清晰窗口。{personality_note}")
            return log

        if primary.action == "retreat":
            unit.position = "safe_cover"
            unit.cover = min(90, unit.cover + 15)
            unit.morale = min(100, unit.morale + 4)
            self._add_status(unit, "retreating")
            log.append(f"{unit.name} 后撤到安全掩体，降低暴露风险。")
            return log

        if primary.action == "suppress":
            target_enemies = self._select_enemies(bf, primary.target or "middle_lane", max_count=3)
            if not target_enemies:
                log.append(f"{unit.name} 尝试压制，但没有找到有效目标。")
                return log
            ammo_cost = 12 if unit.weapon_type == "MG" else 8
            if unit.weapon_type == "MG" and "ammo_hungry" in unit.traits:
                ammo_cost += 2
            if bf.commander_policy in ("conservative", "preserve_hp"):
                ammo_cost = max(4, ammo_cost - 3)
            if unit.ammo < ammo_cost:
                log.append(f"{unit.name} 弹药不足，压制强度下降。")
                ammo_cost = min(unit.ammo, 5)
            unit.ammo = max(0, unit.ammo - ammo_cost)
            for e in target_enemies:
                pressure_gain = 28 if unit.weapon_type == "MG" else 15
                if unit.weapon_type == "MG":
                    pressure_gain += 6
                if unit.personality == "steady":
                    pressure_gain += 4
                e.pressure = min(100, e.pressure + pressure_gain)
                e.exposed = e.pressure >= 45
                if e.shield > 0:
                    shield_hit = 24 if unit.weapon_type == "MG" else 8
                    if "shield_breaker" in unit.traits:
                        shield_hit += 8
                    e.shield = max(0, e.shield - shield_hit)
                else:
                    e.hp = max(0, e.hp - (8 if unit.weapon_type == "MG" else 4))
                self._add_enemy_status(e, "suppressed")
            log.append(f"{unit.name} 压制 {primary.target or '中路'}，敌方推进受阻，装甲稳态/护盾被削弱。{personality_note}")
            return log

        if primary.action == "prioritize_target":
            unit.target_priority = [primary.target or "exposed_enemy"] + [x for x in unit.target_priority if x != primary.target]
            enemy = self._best_target(unit, bf, primary.target)
            if not enemy:
                log.append(f"{unit.name} 调整目标优先级，但暂时没有合适目标。")
                return log
            dmg = self._shoot_damage(unit, enemy)
            enemy.hp = max(0, enemy.hp - dmg)
            ammo_cost = 5 if unit.personality == "cautious" else 6
            unit.ammo = max(0, unit.ammo - ammo_cost)
            enemy.exposed = True if dmg >= 20 else enemy.exposed
            log.append(f"{unit.name} 优先处理 {enemy.name}，造成 {dmg} 伤害。{personality_note}")
            return log

        if primary.action == "focus_fire":
            enemy = self._best_target(unit, bf, primary.target)
            if not enemy:
                log.append(f"{unit.name} 请求集火，但没有锁定目标。")
                return log
            dmg = self._shoot_damage(unit, enemy) + 5
            if enemy.shield > 0:
                shield_hit = min(enemy.shield, dmg)
                enemy.shield -= shield_hit
                remaining = dmg - shield_hit
                enemy.hp = max(0, enemy.hp - remaining)
                log.append(f"{unit.name} 集火 {enemy.name}，削减护盾 {shield_hit}，溢出伤害 {remaining}。")
            else:
                enemy.hp = max(0, enemy.hp - dmg)
                log.append(f"{unit.name} 集火 {enemy.name}，造成 {dmg} 伤害。")
            unit.ammo = max(0, unit.ammo - 8)
            return log

        if primary.action == "flank":
            if unit.weapon_type != "SMG":
                log.append(f"{unit.name} 不适合绕后，改为保持阵位。")
                unit.cover = min(80, unit.cover + 2)
                return log
            blocked = any("do_not_chase" in o.constraints or o.action == "do_not_chase" for o in orders)
            if blocked and unit.discipline > 55:
                log.append(f"{unit.name} 判断追深风险过高，维持左翼阴影，等待窗口。")
                self._add_status(unit, "hidden")
                return log
            if unit.personality == "veteran":
                ready = any(e.exposed or e.pressure >= 45 for e in bf.living_enemies())
                if not ready and bf.commander_policy not in ("aggressive", "rapid_clear"):
                    unit.cover = min(86, unit.cover + 4)
                    self._add_status(unit, "hidden")
                    log.append(f"{unit.name} 没有盲目切入，先贴住左翼阴影等压制窗口。{personality_note}")
                    return log
            unit.position = "enemy_left_flank"
            cover_loss = 6 if unit.personality == "veteran" else 10
            unit.cover = max(25, unit.cover - cover_loss)
            self._add_status(unit, "flanking")
            targets = [e for e in bf.living_enemies() if e.exposed or e.kind == "infantry"]
            if targets:
                enemy = sorted(targets, key=lambda e: (e.kind != "infantry", e.hp))[0]
                dmg = 24 + unit.initiative // 8
                if unit.personality == "veteran":
                    dmg += 5
                enemy.hp = max(0, enemy.hp - dmg)
                enemy.exposed = True
                log.append(f"{unit.name} 从左翼切入，对 {enemy.name} 造成 {dmg} 伤害，并制造侧翼压力。{personality_note}")
            else:
                log.append(f"{unit.name} 绕后到位，但尚未找到安全开火窗口。")
            return log

        if primary.action == "execute":
            enemy = self._best_target(unit, bf, primary.target or "armored")
            if not enemy:
                log.append(f"{unit.name} 等待处决窗口，但目标不存在。")
                return log
            condition_ok = True
            if primary.condition == "enemy_shield_broken":
                condition_ok = enemy.shield <= 0
            if not condition_ok:
                self._add_status(unit, "waiting_execution_window")
                unit.pending_condition = primary.condition
                if unit.personality == "bold" and "do_not_expose_before_condition" not in primary.constraints and bf.commander_policy in ("aggressive", "rapid_clear"):
                    poke = 8
                    enemy.shield = max(0, enemy.shield - poke)
                    unit.cover = max(20, unit.cover - 4)
                    log.append(f"{unit.name} 压不住进攻冲动，试探性逼近 {enemy.name}，削掉 {poke} 护盾但暴露上升。{personality_note}")
                else:
                    log.append(f"{unit.name} 未提前暴露，继续等待 {enemy.name} 破盾后的处决窗口。{personality_note}")
                return log
            burst = 38 + unit.initiative // 6
            if "elite_killer" in unit.traits and enemy.kind in ("armored", "elite"):
                burst += 12
            if unit.personality == "bold":
                burst += 6
                unit.cover = max(20, unit.cover - 5)
            enemy.hp = max(0, enemy.hp - burst)
            unit.ammo = max(0, unit.ammo - 10)
            self._add_status(unit, "execution_spent")
            log.append(f"{unit.name} 抓住窗口处决 {enemy.name}，短爆发造成 {burst} 伤害。{personality_note}")
            return log

        if primary.action == "advance":
            unit.position = "forward_cover"
            cover_loss = 12 if unit.personality == "bold" else 5 if unit.personality == "cautious" else 8
            unit.cover = max(20, unit.cover - cover_loss)
            self._add_status(unit, "advancing")
            if unit.personality == "bold":
                unit.morale = min(100, unit.morale + 3)
            log.append(f"{unit.name} 推进到前沿掩体，获得视野但暴露上升。{personality_note}")
            return log

        if primary.action == "free_fire":
            enemy = self._best_target(unit, bf, None)
            if enemy:
                dmg = self._shoot_damage(unit, enemy)
                enemy.hp = max(0, enemy.hp - dmg)
                unit.ammo = max(0, unit.ammo - 7)
                log.append(f"{unit.name} 自由开火命中 {enemy.name}，造成 {dmg} 伤害。{personality_note}")
            else:
                log.append(f"{unit.name} 自由开火，但没有有效目标。")
            return log

        log.append(f"{unit.name} 未理解动作 {primary.action}，改为守位。")
        return log

    def _enemy_phase(self, bf: Battlefield) -> list[str]:
        log: list[str] = []
        friendlies = bf.living_friendlies()
        if not friendlies:
            return log

        drone_alive = any(e.kind == "drone" and e.is_alive() for e in bf.enemy_units)
        scanner_bonus = 6 if drone_alive else 0

        for enemy in bf.living_enemies():
            if enemy.pressure >= 70:
                enemy.status = ["pinned"]
                log.append(f"{enemy.name} 被强压制，推进失败。")
                enemy.pressure = max(0, enemy.pressure - 15)
                continue

            if enemy.kind == "drone":
                target = max(friendlies, key=lambda u: u.initiative)
                self._add_status(target, "spotted")
                log.append(f"{enemy.name} 继续侦察，{target.name} 暴露风险上升。")
                continue

            # Enemy chooses target with lower cover or spotted.
            target = sorted(friendlies, key=lambda u: (("spotted" not in u.status), u.cover, -u.risk_preference))[0]
            base = 10 if enemy.kind == "infantry" else 17
            hit_chance = 55 + scanner_bonus - target.cover // 2 - enemy.pressure // 3
            if self.rng.randint(1, 100) <= max(10, hit_chance):
                damage = base + self.rng.randint(0, 6)
                target.hp = max(0, target.hp - damage)
                target.morale = max(0, target.morale - 5)
                log.append(f"{enemy.name} 攻击 {target.name} 命中，造成 {damage} 伤害。")
            else:
                log.append(f"{enemy.name} 攻击 {target.name}，被掩体/压制影响而偏出。")

            if enemy.kind == "armored" and enemy.pressure < 50:
                if "enemy_at_core_edge" not in bf.global_status and bf.tick >= 8:
                    bf.global_status.append("enemy_at_core_edge")
                log.append(f"{enemy.name} 继续向核心区域压迫。")

            enemy.pressure = max(0, enemy.pressure - 10)

        return log

    def _cleanup_status(self, bf: Battlefield) -> None:
        # Keep meaningful status but remove temporary spotted sometimes.
        for u in bf.friendly_units:
            if "spotted" in u.status and self.rng.random() < 0.45:
                u.status.remove("spotted")
        for e in bf.enemy_units:
            if not e.is_alive():
                e.status = ["down"]

    def _select_enemies(self, bf: Battlefield, target: str, max_count: int = 1) -> list[Enemy]:
        enemies = bf.living_enemies()
        if not enemies:
            return []
        target = (target or "").lower()
        if target in ("middle_lane", "middle", "中路"):
            candidates = [e for e in enemies if e.position == "middle_lane"]
        elif target in ("drone", "无人机", "air"):
            candidates = [e for e in enemies if e.kind == "drone"]
        elif target in ("armored", "装甲"):
            candidates = [e for e in enemies if e.kind == "armored"]
        elif target in ("infantry", "步兵"):
            candidates = [e for e in enemies if e.kind == "infantry"]
        elif target in ("exposed_enemy", "exposed", "暴露"):
            candidates = [e for e in enemies if e.exposed]
        else:
            candidates = enemies
        return candidates[:max_count] if candidates else enemies[:max_count]

    def _best_target(self, unit: Unit, bf: Battlefield, requested: str | None) -> Enemy | None:
        candidates = self._select_enemies(bf, requested or (unit.target_priority[0] if unit.target_priority else ""), max_count=99)
        if not candidates:
            return None

        def score(e: Enemy) -> int:
            s = 0
            if e.kind in unit.target_priority:
                s += 30
            if requested and requested.lower() in (e.kind, e.position, e.name.lower()):
                s += 40
            if e.exposed:
                s += 25
            if e.kind == "drone" and "anti_drone" in unit.traits:
                s += 40
            if e.kind == "armored" and unit.weapon_type in ("MG", "HG"):
                s += 20
            s += max(0, 100 - e.hp) // 4
            s -= e.cover // 4
            s -= e.shield // 5
            return s

        return sorted(candidates, key=score, reverse=True)[0]

    def _shoot_damage(self, unit: Unit, enemy: Enemy) -> int:
        base_by_weapon = {
            "HG": 18,
            "SMG": 17,
            "AR": 20,
            "MG": 14,
            "RF": 30,
            "SG": 16,
        }
        base = base_by_weapon.get(unit.weapon_type, 15)
        acc_bonus = unit.accuracy // 10
        exposed_bonus = 10 if enemy.exposed else 0
        cover_penalty = enemy.cover // 8
        shield_penalty = enemy.shield // 12
        damage = base + acc_bonus + exposed_bonus - cover_penalty - shield_penalty
        if unit.personality == "cautious":
            damage += 3
        if unit.personality == "bold" and enemy.exposed:
            damage += 4
        return max(4, damage)

    def _personality_note(self, unit: Unit) -> str:
        notes = {
            "bold": "鲁莽性格让她更敢压窗口，但更容易暴露。",
            "cautious": "谨慎性格让她更重视掩体和稳定射击。",
            "veteran": "老练性格让她优先等待协同窗口。",
            "steady": "稳定性格让压制节奏更持续。",
            "rookie": "新人性格让她更依赖明确命令。",
        }
        note = notes.get(unit.personality)
        return f" [{note}]" if note else ""

    def _add_status(self, unit: Unit, status: str) -> None:
        if status not in unit.status:
            unit.status.append(status)

    def _add_enemy_status(self, enemy: Enemy, status: str) -> None:
        if status not in enemy.status:
            enemy.status.append(status)
