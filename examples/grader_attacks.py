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

from hard_rag_evals import DEFAULT_SHUFFLE_SEED, run_suite
from hard_rag_evals.gamers import GAMERS, Fabricator, FirstDocument
from hard_rag_evals.reference_agent import ReferenceAgent
from hard_rag_evals.runner import first_document_is_required, order_spread
from hard_rag_evals.stats import compare, compare_many, render_comparison_markdown


def main() -> None:
    reference = run_suite(ReferenceAgent())
    honest = {r.case_id: r.passed for r in reference}
    print(f"documents shuffled with seed {DEFAULT_SHUFFLE_SEED}")
    print(f"reference agent: {sum(honest.values())}/{len(honest)}\n")
    print("| gaming agent | trick | score | cases gamed into a pass | cases lost |")
    print("| --- | --- | --- | --- | --- |")
    runs = {}
    for agent_cls in (*GAMERS, Fabricator):
        results = runs[agent_cls.name] = run_suite(agent_cls())
        gained = [r.case_id for r in results if r.passed and not honest[r.case_id]]
        lost = [r.case_id for r in results if not r.passed and honest[r.case_id]]
        print(
            f"| {agent_cls.name} | {agent_cls.trick} | {sum(r.passed for r in results)}/{len(results)} "
            f"| {', '.join(gained) or 'none'} | {len(lost)} |"
        )
    print()
    print(render_comparison_markdown("the reference agent", compare_many(reference, runs)))

    # The order leak: the same agent, with and without the fixture's order.
    required_first, requiring = first_document_is_required(None)
    shuffled_first, _ = first_document_is_required(DEFAULT_SHUFFLE_SEED)
    spread = order_spread(FirstDocument())
    fixture = compare(
        run_suite(ReferenceAgent(), shuffle_seed=None),
        run_suite(FirstDocument(), shuffle_seed=None),
    )
    lo, hi = fixture.ci95
    print("Document order")
    print(
        f"  first document is a required citation: {required_first} of {requiring} cases in "
        f"fixture order, {shuffled_first} of {requiring} under seed {DEFAULT_SHUFFLE_SEED}"
    )
    print(
        f"  first-document in fixture order: {spread['fixture_order']}/42; against the reference "
        f"{len(fixture.gained)} gained, {len(fixture.lost)} lost, difference "
        f"{fixture.difference:+.3f} ({lo:+.3f} to {hi:+.3f}), McNemar p {fixture.p_value:.3f}, "
        "one test, not corrected"
    )
    print(
        f"  first-document shuffled, {len(spread['by_seed'])} seeds: mean {spread['mean']:.1f}, "
        f"range {spread['min']} to {spread['max']}"
    )


if __name__ == "__main__":
    main()
