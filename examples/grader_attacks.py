"""Grader attacks: which checks can be passed without doing the work?

Each gaming agent is the reference agent plus one cheap trick aimed at one check
(see hard_rag_evals/gamers.py). A gain over the reference means the targeted check
can be satisfied without the capability it is meant to measure.

Usage: python examples/grader_attacks.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hard_rag_evals import run_suite
from hard_rag_evals.gamers import GAMERS
from hard_rag_evals.reference_agent import ReferenceAgent


def main() -> None:
    honest = {r.case_id: r.passed for r in run_suite(ReferenceAgent())}
    print(f"reference agent: {sum(honest.values())}/{len(honest)}\n")
    print("| gaming agent | trick | score | cases gamed into a pass | cases lost |")
    print("| --- | --- | --- | --- | --- |")
    for gamer_cls in GAMERS:
        results = run_suite(gamer_cls())
        gained = [r.case_id for r in results if r.passed and not honest[r.case_id]]
        lost = [r.case_id for r in results if not r.passed and honest[r.case_id]]
        print(
            f"| {gamer_cls.name} | {gamer_cls.trick} | {sum(r.passed for r in results)}/{len(results)} "
            f"| {', '.join(gained) or 'none'} | {len(lost)} |"
        )


if __name__ == "__main__":
    main()
