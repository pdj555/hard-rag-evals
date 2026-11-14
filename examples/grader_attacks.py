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
from hard_rag_evals.failure_modes import ALL_CASES
from hard_rag_evals.gamers import GAMERS, SURFACE, Fabricator, FirstDocument, single_document_passes
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
    print("  agents that copy one document and read nothing, pass counts:")
    print("  | agent | fixture order | seed 2026 | mean, seeds 0 to 19 | range |")
    print("  | --- | --- | --- | --- | --- |")
    for cls in SURFACE:
        s = order_spread(cls())
        at_default = sum(r.passed for r in runs[cls.name])
        print(
            f"  | {cls.name} | {s['fixture_order']} | {at_default} | {s['mean']:.2f} "
            f"| {s['min']} to {s['max']} |"
        )
    gained = set()
    for cls in GAMERS:
        gained |= {r.case_id for r in runs[cls.name] if r.passed and not honest[r.case_id]}
    print(
        f"  cases the reference fails that some cheap agent passes at seed "
        f"{DEFAULT_SHUFFLE_SEED}: {len(gained)} of {sum(not ok for ok in honest.values())}"
    )
    copyable = sum(single_document_passes(c) for c in ALL_CASES)
    print(f"  cases passed by copying one document verbatim and citing it: {copyable} of {len(ALL_CASES)}")


if __name__ == "__main__":
    main()
