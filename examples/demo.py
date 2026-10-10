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
    DIFFICULTY_ORDER,
    Answer,
    Corpus,
    RetrievalBudget,
    render_markdown,
    run_suite,
    summary_by_difficulty,
)
from hard_rag_evals.reference_agent import ReferenceAgent


class FabricatingAgent(ReferenceAgent):
    """Wraps the reference agent and appends a citation to a document
    that does not exist. Demonstrates that the fabrication check fires
    even when the answer text is otherwise fine."""

    name = "fabricating-agent"

    def answer(
        self, query: str, corpus: Corpus, budget: RetrievalBudget
    ) -> Answer:
        ans = super().answer(query, corpus, budget)
        ans.citations = ans.citations + ["doc-does-not-exist-99"]
        return ans


def main() -> None:
    for agent in (ReferenceAgent(), FabricatingAgent()):
        results = run_suite(agent)
        report = render_markdown(agent.name, results)
        out = Path(__file__).parent / f"run_report_{agent.name}.md"
        out.write_text(report)
        print(f"wrote {out}")

        print(f"\n{agent.name} tier progression:")
        for tier in DIFFICULTY_ORDER:
            p, t = summary_by_difficulty(results)[tier]
            bar = "#" * p + "-" * (t - p)
            print(f"  {tier:8s} {p:2d}/{t:2d} [{bar}]")
        print()


if __name__ == "__main__":
    main()
