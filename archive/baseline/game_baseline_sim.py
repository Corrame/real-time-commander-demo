from __future__ import annotations

from dataclasses import dataclass
import random
from statistics import mean


@dataclass(frozen=True)
class BaselineConfig:
    name: str
    max_rounds: int
    friendly_hp: int
    enemy_hp: int
    base_damage: int
    damage_jitter: int = 0
    hit_chance: float = 1.0
    crit_chance: float = 0.0
    crit_bonus: int = 0


@dataclass(frozen=True)
class BattleResult:
    winner: str
    rounds: int
    friendly_hp: int
    enemy_hp: int


@dataclass(frozen=True)
class BatchStats:
    config_name: str
    runs: int
    friendly_wins: int
    enemy_wins: int
    draws: int
    friendly_win_rate: float
    enemy_win_rate: float
    draw_rate: float
    avg_rounds: float
    avg_friendly_hp: float
    avg_enemy_hp: float
    avg_winner_hp: float


CONFIGS = {
    "0.1": BaselineConfig(
        name="0.1-deterministic-near-mutual-kill",
        max_rounds=10,
        friendly_hp=100,
        enemy_hp=100,
        base_damage=10,
    ),
    "0.2": BaselineConfig(
        name="0.2-stochastic-fifty-fifty",
        max_rounds=12,
        friendly_hp=80,
        enemy_hp=80,
        base_damage=10,
        damage_jitter=2,
        hit_chance=0.88,
        crit_chance=0.10,
        crit_bonus=4,
    ),
}


def simulate_battle(config: BaselineConfig, rng: random.Random) -> BattleResult:
    friendly_hp = config.friendly_hp
    enemy_hp = config.enemy_hp

    for round_no in range(1, config.max_rounds + 1):
        friendly_damage = roll_damage(config, rng)
        enemy_damage = roll_damage(config, rng)

        # Simultaneous resolution: both sides commit damage before casualties are checked.
        enemy_hp = max(0, enemy_hp - friendly_damage)
        friendly_hp = max(0, friendly_hp - enemy_damage)

        if friendly_hp <= 0 and enemy_hp <= 0:
            return BattleResult("draw", round_no, friendly_hp, enemy_hp)
        if enemy_hp <= 0:
            return BattleResult("friendly", round_no, friendly_hp, enemy_hp)
        if friendly_hp <= 0:
            return BattleResult("enemy", round_no, friendly_hp, enemy_hp)

    if friendly_hp > enemy_hp:
        winner = "friendly"
    elif enemy_hp > friendly_hp:
        winner = "enemy"
    else:
        winner = "draw"
    return BattleResult(winner, config.max_rounds, friendly_hp, enemy_hp)


def roll_damage(config: BaselineConfig, rng: random.Random) -> int:
    if rng.random() > config.hit_chance:
        return 0
    jitter = rng.randint(-config.damage_jitter, config.damage_jitter) if config.damage_jitter else 0
    damage = max(0, config.base_damage + jitter)
    if rng.random() < config.crit_chance:
        damage += config.crit_bonus
    return damage


def run_batch(config: BaselineConfig, runs: int, seed: int) -> BatchStats:
    rng = random.Random(seed)
    results = [simulate_battle(config, rng) for _ in range(runs)]
    friendly_wins = sum(1 for result in results if result.winner == "friendly")
    enemy_wins = sum(1 for result in results if result.winner == "enemy")
    draws = runs - friendly_wins - enemy_wins
    winner_hps = [
        result.friendly_hp if result.winner == "friendly" else result.enemy_hp
        for result in results
        if result.winner != "draw"
    ]

    return BatchStats(
        config_name=config.name,
        runs=runs,
        friendly_wins=friendly_wins,
        enemy_wins=enemy_wins,
        draws=draws,
        friendly_win_rate=friendly_wins / runs,
        enemy_win_rate=enemy_wins / runs,
        draw_rate=draws / runs,
        avg_rounds=mean(result.rounds for result in results),
        avg_friendly_hp=mean(result.friendly_hp for result in results),
        avg_enemy_hp=mean(result.enemy_hp for result in results),
        avg_winner_hp=mean(winner_hps) if winner_hps else 0.0,
    )
