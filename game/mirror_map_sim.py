from __future__ import annotations

from dataclasses import dataclass
import random
from statistics import mean


@dataclass(frozen=True)
class MapConfig:
    width: int = 7
    height: int = 3
    max_ticks: int = 16


@dataclass(frozen=True)
class UnitSpec:
    role: str
    hp: int
    attack: int
    attack_range: int


@dataclass
class MapUnit:
    id: str
    side: str
    spec: UnitSpec
    x: int
    y: int
    hp: int

    def is_alive(self) -> bool:
        return self.hp > 0


@dataclass(frozen=True)
class UnitCommand:
    mode: str
    target: str | None = None


@dataclass(frozen=True)
class MirrorResult:
    winner: str
    ticks: int
    red_hp: int
    blue_hp: int
    red_alive: int
    blue_alive: int


@dataclass(frozen=True)
class MirrorBatchStats:
    runs: int
    red_wins: int
    blue_wins: int
    draws: int
    red_win_rate: float
    blue_win_rate: float
    draw_rate: float
    avg_ticks: float
    avg_red_hp: float
    avg_blue_hp: float
    avg_winner_hp: float


SPECS = [
    UnitSpec(role="front", hp=36, attack=6, attack_range=2),
    UnitSpec(role="mid", hp=28, attack=7, attack_range=2),
    UnitSpec(role="back", hp=22, attack=8, attack_range=3),
]

COMMAND_MODES = {
    "attack_nearest",
    "focus_weakest",
    "focus_target",
    "hold_position",
    "hold_line",
    "keep_range",
    "retreat",
    "advance",
    "cower",
}

POLICIES = {"dumb", "good_focus", "bad_charge", "hold_all", "cower_all", "hesitate"}


def create_units() -> list[MapUnit]:
    red_positions = [(1, 1), (0, 0), (0, 2)]
    blue_positions = [(5, 1), (6, 0), (6, 2)]
    units: list[MapUnit] = []

    for index, spec in enumerate(SPECS):
        x, y = red_positions[index]
        units.append(MapUnit(id=f"R{index + 1}", side="red", spec=spec, x=x, y=y, hp=spec.hp))

    for index, spec in enumerate(SPECS):
        x, y = blue_positions[index]
        units.append(MapUnit(id=f"B{index + 1}", side="blue", spec=spec, x=x, y=y, hp=spec.hp))

    return units


def simulate_mirror_battle(
    seed: int = 42,
    config: MapConfig | None = None,
    jitter: int = 0,
    red_policy: str = "dumb",
    blue_policy: str = "dumb",
) -> MirrorResult:
    config = config or MapConfig()
    validate_policy(red_policy)
    validate_policy(blue_policy)
    rng = random.Random(seed)
    units = create_units()

    for tick in range(1, config.max_ticks + 1):
        alive = [unit for unit in units if unit.is_alive()]
        red_alive = [unit for unit in alive if unit.side == "red"]
        blue_alive = [unit for unit in alive if unit.side == "blue"]
        if not red_alive or not blue_alive:
            return summarize(units, tick - 1)

        damage_rolls = paired_damage_rolls(rng, jitter)
        attacks: list[tuple[MapUnit, MapUnit, int]] = []
        moves: list[tuple[MapUnit, int, int]] = []

        for unit in alive:
            enemies = blue_alive if unit.side == "red" else red_alive
            allies = red_alive if unit.side == "red" else blue_alive
            policy = red_policy if unit.side == "red" else blue_policy
            command = command_for(unit, allies, enemies, policy, tick)
            if command.mode == "cower":
                continue
            target = choose_target(unit, enemies, command)
            if distance(unit, target) <= unit.spec.attack_range:
                damage = damage_rolls.get(unit.id, unit.spec.attack)
                attacks.append((unit, target, damage))
            else:
                step = next_step_for_command(unit, target, enemies, command, config)
                if step != (unit.x, unit.y):
                    moves.append((unit, *step))

        apply_simultaneous_moves(moves, alive)

        damage_by_id: dict[str, int] = {}
        target_by_id = {unit.id: unit for unit in units}
        for attacker, target, damage in attacks:
            if attacker.is_alive() and target.is_alive():
                damage_by_id[target.id] = damage_by_id.get(target.id, 0) + damage

        for target_id, damage in damage_by_id.items():
            target_by_id[target_id].hp = max(0, target_by_id[target_id].hp - damage)

    return summarize(units, config.max_ticks)


def paired_damage_rolls(rng: random.Random, jitter: int) -> dict[str, int]:
    rolls: dict[str, int] = {}
    for index, spec in enumerate(SPECS, start=1):
        if jitter:
            pair = [
                max(0, spec.attack + rng.randint(-jitter, jitter)),
                max(0, spec.attack + rng.randint(-jitter, jitter)),
            ]
            if rng.random() < 0.5:
                pair.reverse()
        else:
            pair = [spec.attack, spec.attack]
        rolls[f"R{index}"] = pair[0]
        rolls[f"B{index}"] = pair[1]
    return rolls


def apply_simultaneous_moves(moves: list[tuple[MapUnit, int, int]], alive: list[MapUnit]) -> None:
    start_positions = {(unit.x, unit.y): unit for unit in alive}
    destinations: dict[tuple[int, int], list[MapUnit]] = {}
    moving_from = {(unit.x, unit.y) for unit, _, _ in moves}

    for unit, nx, ny in moves:
        destinations.setdefault((nx, ny), []).append(unit)

    for (nx, ny), claimants in destinations.items():
        if len(claimants) != 1:
            continue
        unit = claimants[0]
        occupant = start_positions.get((nx, ny))
        if occupant is not None and (nx, ny) not in moving_from:
            continue
        unit.x = nx
        unit.y = ny


def validate_policy(policy: str) -> None:
    if policy not in POLICIES:
        allowed = ", ".join(sorted(POLICIES))
        raise ValueError(f"Unknown policy {policy!r}. Allowed: {allowed}")


def command_for(unit: MapUnit, allies: list[MapUnit], enemies: list[MapUnit], policy: str, tick: int) -> UnitCommand:
    if policy == "good_focus":
        if unit.spec.role == "front":
            return UnitCommand("hold_line")
        if unit.spec.role == "mid":
            return UnitCommand("focus_weakest")
        return UnitCommand("keep_range", target="weakest")
    if policy == "bad_charge":
        return UnitCommand("advance", target="back")
    if policy == "hold_all":
        return UnitCommand("hold_position")
    if policy == "cower_all":
        return UnitCommand("cower")
    if policy == "hesitate" and tick <= 2:
        return UnitCommand("cower")
    return UnitCommand("attack_nearest")


def choose_target(unit: MapUnit, enemies: list[MapUnit], command: UnitCommand) -> MapUnit:
    if command.target and command.target not in ("weakest", "nearest"):
        for enemy in enemies:
            if enemy.id == command.target or enemy.spec.role == command.target:
                return enemy
    if command.mode == "focus_weakest" or command.target == "weakest":
        return sorted(enemies, key=lambda enemy: (enemy.hp, distance(unit, enemy), enemy.id))[0]
    return sorted(enemies, key=lambda enemy: (distance(unit, enemy), enemy.hp, enemy.id))[0]


def next_step_for_command(
    unit: MapUnit,
    target: MapUnit,
    enemies: list[MapUnit],
    command: UnitCommand,
    config: MapConfig,
) -> tuple[int, int]:
    if command.mode == "hold_position":
        return unit.x, unit.y
    if command.mode == "cower":
        return unit.x, unit.y
    if command.mode == "hold_line":
        guard_x = 2 if unit.side == "red" else config.width - 3
        if unit.x != guard_x:
            return unit.x + sign(guard_x - unit.x), unit.y
        return unit.x, unit.y
    if command.mode == "retreat":
        return retreat_step(unit, config)
    if command.mode == "keep_range":
        nearest = sorted(enemies, key=lambda enemy: distance(unit, enemy))[0]
        if distance(unit, nearest) <= max(1, unit.spec.attack_range - 1):
            return retreat_step(unit, config)
        if distance(unit, target) > unit.spec.attack_range:
            return next_step(unit, target, config)
        return unit.x, unit.y
    return next_step(unit, target, config)


def retreat_step(unit: MapUnit, config: MapConfig) -> tuple[int, int]:
    home_x = 0 if unit.side == "red" else config.width - 1
    dx = sign(home_x - unit.x)
    if dx:
        return unit.x + dx, unit.y
    return unit.x, unit.y


def next_step(unit: MapUnit, target: MapUnit, config: MapConfig) -> tuple[int, int]:
    dx = sign(target.x - unit.x)
    dy = sign(target.y - unit.y)
    candidates = [
        (unit.x + dx, unit.y),
        (unit.x, unit.y + dy),
        (unit.x + dx, unit.y + dy),
    ]
    valid = [
        (x, y)
        for x, y in candidates
        if 0 <= x < config.width and 0 <= y < config.height and (x, y) != (unit.x, unit.y)
    ]
    if not valid:
        return unit.x, unit.y
    return sorted(valid, key=lambda pos: abs(pos[0] - target.x) + abs(pos[1] - target.y))[0]


def sign(value: int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def distance(a: MapUnit, b: MapUnit) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


def summarize(units: list[MapUnit], ticks: int) -> MirrorResult:
    red_hp = sum(unit.hp for unit in units if unit.side == "red" and unit.is_alive())
    blue_hp = sum(unit.hp for unit in units if unit.side == "blue" and unit.is_alive())
    red_alive = sum(1 for unit in units if unit.side == "red" and unit.is_alive())
    blue_alive = sum(1 for unit in units if unit.side == "blue" and unit.is_alive())

    if red_alive and not blue_alive:
        winner = "red"
    elif blue_alive and not red_alive:
        winner = "blue"
    elif red_hp > blue_hp:
        winner = "red"
    elif blue_hp > red_hp:
        winner = "blue"
    else:
        winner = "draw"

    return MirrorResult(
        winner=winner,
        ticks=ticks,
        red_hp=red_hp,
        blue_hp=blue_hp,
        red_alive=red_alive,
        blue_alive=blue_alive,
    )


def run_batch(
    runs: int,
    seed: int,
    jitter: int = 0,
    red_policy: str = "dumb",
    blue_policy: str = "dumb",
) -> MirrorBatchStats:
    if runs <= 0:
        raise ValueError("runs must be greater than 0")

    results = [
        simulate_mirror_battle(
            seed=seed + index,
            jitter=jitter,
            red_policy=red_policy,
            blue_policy=blue_policy,
        )
        for index in range(runs)
    ]
    red_wins = sum(1 for result in results if result.winner == "red")
    blue_wins = sum(1 for result in results if result.winner == "blue")
    draws = runs - red_wins - blue_wins
    winner_hps = [
        result.red_hp if result.winner == "red" else result.blue_hp
        for result in results
        if result.winner != "draw"
    ]

    return MirrorBatchStats(
        runs=runs,
        red_wins=red_wins,
        blue_wins=blue_wins,
        draws=draws,
        red_win_rate=red_wins / runs,
        blue_win_rate=blue_wins / runs,
        draw_rate=draws / runs,
        avg_ticks=mean(result.ticks for result in results),
        avg_red_hp=mean(result.red_hp for result in results),
        avg_blue_hp=mean(result.blue_hp for result in results),
        avg_winner_hp=mean(winner_hps) if winner_hps else 0.0,
    )
