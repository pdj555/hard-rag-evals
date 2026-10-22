"""Game the grader: pass contradiction cases without detecting any contradiction.

The contradiction check passes an answer that cites both conflicting documents
and uses a marker word like "however". This agent is the reference agent plus
two moves: cite every retrieved document, and append one hedging sentence. It
learns nothing about the corpus.

Usage: python examples/game_the_grader.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hard_rag_evals import run_suite
from hard_rag_evals.gamers import Hedger as MarkerGamer
from hard_rag_evals.reference_agent import ReferenceAgent


def main() -> None:
    honest = {r.case_id: r.passed for r in run_suite(ReferenceAgent())}
    gamed = run_suite(MarkerGamer())
    print(f"reference agent: {sum(honest.values())}/{len(honest)}")
    print(f"marker gamer:    {sum(r.passed for r in gamed)}/{len(gamed)}")
    for r in gamed:
        if r.passed and not honest[r.case_id]:
            print(f"  gamed into a pass: {r.case_id}")
        if not r.passed and honest[r.case_id]:
            print(f"  lost:              {r.case_id} ({'; '.join(r.notes)})")


if __name__ == "__main__":
    main()
