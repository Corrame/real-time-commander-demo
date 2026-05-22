from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Unit:
    id: str
    name: str
    side: str
    weapon_type: str
    hp: int
    ammo: int
    position: str
    cover: int
    morale: int
    status: list[str]
    personality: str
    role: str
    risk_preference: int
    discipline: int
    initiative: int
    accuracy: int
    mobility: int
    traits: list[str] = field(default_factory=list)
    target_priority: list[str] = field(default_factory=list)
    pending_condition: Optional[str] = None

    def is_alive(self) -> bool:
        return self.hp > 0

    def short(self) -> str:
        tags = ", ".join(self.status) if self.status else "normal"
        return f"{self.name}({self.weapon_type}) HP {self.hp}% Ammo {self.ammo}% Pos:{self.position} Cover:{self.cover} [{tags}]"


@dataclass
class Enemy:
    id: str
    name: str
    kind: str
    hp: int
    shield: int
    position: str
    cover: int
    pressure: int = 0
    exposed: bool = False
    status: list[str] = field(default_factory=list)

    def is_alive(self) -> bool:
        return self.hp > 0

    def short(self) -> str:
        tags = ", ".join(self.status) if self.status else "normal"
        exposed = " exposed" if self.exposed else ""
        return f"{self.name} HP {self.hp}% Shield {self.shield}% Pos:{self.position} Cover:{self.cover} Pressure:{self.pressure}{exposed} [{tags}]"


@dataclass
class Order:
    unit: str
    action: str
    target: Optional[str] = None
    condition: Optional[str] = None
    constraints: list[str] = field(default_factory=list)
    priority: int = 1
    raw_text: str = ""


@dataclass
class Battlefield:
    tick: int
    max_tick: int
    location: str
    friendly_units: list[Unit]
    enemy_units: list[Enemy]
    global_status: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    commander_policy: str = "balanced"

    def living_friendlies(self) -> list[Unit]:
        return [u for u in self.friendly_units if u.is_alive()]

    def living_enemies(self) -> list[Enemy]:
        return [e for e in self.enemy_units if e.is_alive()]
