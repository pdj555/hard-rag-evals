"""The suite as an MCP server, on stdio: `hard-rag-evals mcp`.

Needs the optional extra: pip install 'hard-rag-evals[mcp]'. Three tools let
an agent take the eval without any Python glue: list the cases, fetch one
case's question and documents, and submit an answer for grading.

get_case never returns a case's gates or gold document ids. grade_answer
returns the verdict and the names of the failed gates; the notes that say
which document was missing or forbidden are returned only when explain is
true, because an agent that reads them and resubmits is being told the
answer key. Leave explain off for a score that means anything.
"""
from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import report as R
from .failure_modes import ALL_CASES
from .provenance import GRADER_VERSION
from .runner import DIFFICULTY_ORDER, grade, select_cases


def _case(case_id: str):
    for case in ALL_CASES:
        if case.id == case_id:
            return case
    raise ToolError(f"unknown case {case_id!r}; call list_cases for the ids")


def build_server() -> MCPServer:
    server = MCPServer(
        "hard-rag-evals",
        instructions=(
            "Deterministic RAG eval, 42 cases. Call list_cases, then get_case for the "
            "question and documents, answer from the documents only, and submit with "
            "grade_answer. Cite document ids. Set abstained when the documents do not "
            "hold the answer."
        ),
        version=GRADER_VERSION,
    )

    @server.tool()
    def list_cases(difficulty: str | None = None, mode: str | None = None) -> dict[str, Any]:
        """List the eval cases: id, tier, failure mode, question, document
        count and retrieval budget. Filter by difficulty (easy, medium, hard,
        brutal) or by failure mode."""
        if difficulty is not None and difficulty not in DIFFICULTY_ORDER:
            raise ToolError(f"unknown difficulty {difficulty!r}; one of {DIFFICULTY_ORDER}")
        cases = select_cases(difficulty, mode)
        if not cases:
            raise ToolError(f"no case has mode {mode!r}")
        return R.case_list_document(cases)

    @server.tool()
    def get_case(case_id: str) -> dict[str, Any]:
        """One case as the agent under test sees it: the question, every
        document with its id, source and published date, and the retrieval
        budget. Does not include what the grader checks."""
        return R.case_document(_case(case_id))

    @server.tool()
    def grade_answer(
        case_id: str,
        text: str,
        citations: list[str] | None = None,
        abstained: bool = False,
        retrieved_ids: list[str] | None = None,
        explain: bool = False,
    ) -> dict[str, Any]:
        """Grade one answer. citations are the ids of the documents the answer
        relies on. Set abstained to true when the documents do not hold the
        answer. Returns passed, the gates that applied and the ones that
        failed, the four scores, and the grader version. With explain true
        it also returns notes naming the documents involved, which gives away
        part of the answer key."""
        _, answer = R.parse_answer(
            {
                "case_id": case_id,
                "text": text,
                "citations": citations or [],
                "abstained": abstained,
                "retrieved_ids": retrieved_ids or [],
            },
            "grade_answer",
        )
        result = R.result_dict(grade(_case(case_id), answer))
        if not explain:
            result["notes"] = ["notes withheld; pass explain=true to see them"]
        return result

    return server


def main() -> None:
    build_server().run("stdio")


if __name__ == "__main__":
    main()
