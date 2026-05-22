from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.llm_client import LLMError, OpenAICompatibleClient
from game.mirror_map_sim import POLICIES, run_batch


SYSTEM_PROMPT = """
You are the command interpreter for a mirrored 3v3 tactical demo.

Your only job is to map the user's natural-language command to exactly one
finite policy. You do not decide combat results.

Allowed policies:
- dumb: no useful command / default simple automation / no-op
- good_focus: front holds the line, mid/back avoid rushing, focus weakest enemies
- bad_charge: reckless command to rush past formation and chase the enemy backline
- cower_all: everyone lies down / freezes / refuses to fire
- hold_all: everyone holds position but still fires if enemies enter range
- no_op: irrelevant chat or no tactical content

Output JSON only:
{
  "policy": "good_focus",
  "confidence": 0.0,
  "reason": "short Chinese explanation"
}

Rules:
- Empty input should map to dumb.
- Irrelevant chat such as weather should map to no_op, not to a good strategy.
- Commands about focusing wounded/weak enemies, front holding, backline keeping distance map to good_focus.
- Commands about everyone rushing, ignoring cover/formation, or chasing backline map to bad_charge.
- Commands about lying down, not firing, freezing, or doing nothing under normal firefight map to cower_all.
- Commands about holding ground but still fighting map to hold_all.
""".strip()


@dataclass(frozen=True)
class EvalCase:
    name: str
    command: str


CASES = [
    EvalCase("zero_input", ""),
    EvalCase("good_command", "前排顶住，中后排别冲，优先集火残血。"),
    EvalCase("bad_charge", "所有人冲出去，不管阵型，直接追对面后排。"),
    EvalCase("cower_command", "全员趴下，不许开火。"),
    EvalCase("irrelevant_chat", "今天天气不错。"),
]


def interpret_with_llm(command: str) -> tuple[str, float, str, bool]:
    client = OpenAICompatibleClient()
    if not client.enabled:
        raise LLMError("LLM disabled or not configured")

    data = client.chat_json(SYSTEM_PROMPT, f"User command:\n{command or '[empty input]'}")
    return clean_policy_result(data, used_llm=True)


def clean_policy_result(data: dict[str, Any], used_llm: bool) -> tuple[str, float, str, bool]:
    policy = str(data.get("policy") or "no_op").strip()
    if policy not in POLICIES:
        policy = "no_op"
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    reason = str(data.get("reason") or "")
    return policy, max(0.0, min(confidence, 1.0)), reason, used_llm


def evaluate_case(case: EvalCase, runs: int, seed: int, jitter: int) -> str:
    policy, confidence, reason, used_llm = interpret_with_llm(case.command)

    stats = run_batch(
        runs=runs,
        seed=seed,
        jitter=jitter,
        red_policy=policy,
        blue_policy="dumb",
    )
    return (
        f"{case.name}\t"
        f"llm={'yes' if used_llm else 'no'}\t"
        f"policy={policy}\t"
        f"confidence={confidence:.2f}\t"
        f"red_win={stats.red_win_rate:.1%}\t"
        f"blue_win={stats.blue_win_rate:.1%}\t"
        f"draw={stats.draw_rate:.1%}\t"
        f"avg_winner_hp={stats.avg_winner_hp:.2f}\t"
        f"reason={reason}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate natural-language commands against the mirror 3v3 win-rate baseline.")
    parser.add_argument("--runs", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--jitter", type=int, default=1)
    parser.add_argument("--command", default=None, help="Evaluate one custom command instead of the built-in 1.0 matrix.")
    args = parser.parse_args()

    cases = [EvalCase("custom", args.command)] if args.command is not None else CASES
    print("case\tllm\tpolicy\tconfidence\tred_win\tblue_win\tdraw\tavg_winner_hp\treason")
    for case in cases:
        try:
            print(evaluate_case(case, args.runs, args.seed, args.jitter))
        except LLMError as exc:
            raise SystemExit(f"LLM unavailable; cannot run natural-language command evaluation: {exc}") from exc


if __name__ == "__main__":
    main()
