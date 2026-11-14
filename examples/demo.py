"""Demo: run the full suite against the reference agent, plus a
fabricating variant that shows the citation check working.

Prints the tier progression (easy / medium / hard / brutal) so you can
see where the baseline breaks, then writes per-agent markdown reports.

Usage: python examples/demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hard_rag_evals import (
    DEFAULT_SHUFFLE_SEED,
    DIFFICULTY_ORDER,
    render_markdown,
    run_suite,
    summary_by_difficulty,
)
from hard_rag_evals.gamers import Fabricator
from hard_rag_evals.reference_agent import ReferenceAgent
from hard_rag_evals.runner import order_spread
from hard_rag_evals.stats import clopper_pearson, pass_rate


def main() -> None:
    for agent in (ReferenceAgent(), Fabricator()):
        results = run_suite(agent)
        report = render_markdown(agent.name, results)
        out = Path(__file__).parent / f"run_report_{agent.name}.md"
        out.write_text(report)
        print(f"wrote {out}")

        print(f"\n{agent.name} tier progression, documents shuffled with seed {DEFAULT_SHUFFLE_SEED}:")
        for tier in DIFFICULTY_ORDER:
            p, t = summary_by_difficulty(results)[tier]
            bar = "#" * p + "-" * (t - p)
            lo, hi = clopper_pearson(p, t)
            print(f"  {tier:8s} {p:2d}/{t:2d} [{bar}]  95% interval {lo:.2f} to {hi:.2f}")
        overall = pass_rate(results)
        lo, hi = overall["ci95"]
        print(
            f"  {'all':8s} {overall['passed']:2d}/{overall['total']:2d}  "
            f"95% interval {lo:.2f} to {hi:.2f}"
        )
        spread = order_spread(agent)
        print(
            f"  fixture order: {spread['fixture_order']} passed. "
            f"{len(spread['by_seed'])} other seeds: {spread['min']} to {spread['max']} passed, "
            f"{len(spread['flipped'])} cases changed verdict against fixture order"
        )
        print()


if __name__ == "__main__":
    main()
