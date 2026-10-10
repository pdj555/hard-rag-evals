"""Demo: run the full suite against the reference agent, plus a
fabricating variant that shows the citation check working.

Usage: python examples/demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hard_rag_evals import Answer, Corpus, RetrievalBudget, render_markdown, run_suite
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
        print(report)
        out = Path(__file__).parent / f"run_report_{agent.name}.md"
        out.write_text(report)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
