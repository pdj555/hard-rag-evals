"""The suite as an MCP server, on stdio: `hard-rag-evals mcp`.

Needs the optional extra: pip install 'hard-rag-evals[mcp]'.

By default the server is built for an agent under test, and it is built so
that the agent cannot read the answer key out of it:

- list_cases and get_case give the public view: opaque case ids, the tier,
  the question, the documents and the budget. No failure mode, no
  descriptive id, no gates.
- get_case lists a case's documents in a shuffled order, fixed by a
  published seed. Fixture order would leak: it usually puts a required
  document first.
- grade_submission takes the answers for all 42 cases and returns one
  aggregate: passed and total, with an interval. A submission that leaves
  any case out is refused, and there is no per-tier split. Nothing about any
  single case comes back.
- A server process grades one submission. A second call is refused, and so
  is a call that arrives while the first is still being graded: the slot is
  claimed under a lock before anything is parsed. Without that, two
  submissions that differ in one answer would give that case's verdict by
  subtraction.
- There is no per-case grading tool.

What this does not stop: an agent that can start the server again can still
compare whole submissions, one verdict per pair of runs. get_case returns
every document, so an agent that reads them all is not held to the case's
retrieval budget unless it reports what it read in retrieved_ids. A score is blind only when
the agent cannot restart the grader, which is the operator's job to arrange.

`hard-rag-evals mcp --dev` is for the person writing or debugging cases. It
adds grade_answer, which grades one answer and returns its gates and notes,
shows descriptive ids and failure modes, and lifts the one-submission limit.
grade_answer says which gate failed and names the documents involved; a few
hundred calls recover most of the answer key. Scores from a --dev server
mean nothing.
"""
from __future__ import annotations

import threading
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import report as R
from .failure_modes import ALL_CASES
from .provenance import GRADER_VERSION
from .runner import DEFAULT_SHUFFLE_SEED, DIFFICULTY_ORDER, grade, present, select_cases


def build_server(dev: bool = False) -> MCPServer:
    def find(case_id: str):
        try:
            return R.resolve_case(case_id, ALL_CASES, allow_descriptive=dev)
        except R.UsageError:
            raise ToolError(f"unknown case {case_id!r}; call list_cases for the ids") from None

    server = MCPServer(
        "hard-rag-evals",
        instructions=(
            "Deterministic RAG eval, 42 cases. Call list_cases, then get_case for each "
            "question and its documents. Answer from the documents only, cite document "
            "ids, and set abstained when the documents do not hold the answer. When every "
            "case is answered, call grade_submission once with all the answers; it returns "
            "aggregate counts and can be called once per server."
            + (
                " This server was started with --dev: grade_answer exposes the answer "
                "key, so scores from it mean nothing."
                if dev
                else ""
            )
        ),
        version=GRADER_VERSION,
    )
    # One submission per server process. The SDK runs tools on worker threads,
    # so the slot is claimed under a lock before any work is done.
    slot = {"claimed": False}
    slot_lock = threading.Lock()

    @server.tool()
    def list_cases(difficulty: str | None = None) -> dict[str, Any]:
        """List the eval cases: id, tier, question, document count and
        retrieval budget. Optionally keep one tier (easy, medium, hard,
        brutal)."""
        if difficulty is not None and difficulty not in DIFFICULTY_ORDER:
            raise ToolError(f"unknown difficulty {difficulty!r}; one of {DIFFICULTY_ORDER}")
        return R.case_list_document(select_cases(difficulty), dev=dev)

    @server.tool()
    def get_case(case_id: str) -> dict[str, Any]:
        """One case as the agent under test sees it: the question, every
        document with its id, source and published date, and the retrieval
        budget. Does not include what the grader checks."""
        case = present(find(case_id), DEFAULT_SHUFFLE_SEED)
        return R.case_document(case, dev=dev, shuffle_seed=DEFAULT_SHUFFLE_SEED)

    @server.tool()
    def grade_submission(answers: list[dict[str, Any]]) -> dict[str, Any]:
        """Grade a whole submission and return one aggregate: passed and
        total over all cases, with a 95% interval. Nothing about any single
        case or tier is returned.

        answers: one object for every case, all 42, with case_id (from
        list_cases), text, and optionally citations (document ids), abstained
        (true when the documents do not hold the answer) and retrieved_ids.
        A submission that leaves a case out is refused. This can be called
        once per server."""
        if not dev:
            with slot_lock:
                if slot["claimed"]:
                    raise ToolError(
                        "this server has already graded a submission; it grades one, so that "
                        "two submissions cannot be compared to find a single case's verdict"
                    )
                slot["claimed"] = True
        try:
            return _grade_all(answers)
        except ToolError:
            # A submission that was refused was not graded and told the caller
            # nothing about any case, so it does not use up the slot.
            with slot_lock:
                slot["claimed"] = False
            raise

    def _grade_all(answers: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            parsed = [R.parse_answer(a, f"answers[{i}]") for i, a in enumerate(answers)]
        except R.UsageError as exc:
            raise ToolError(str(exc)) from None
        by_case = {}
        for given_id, answer in parsed:
            case = find(given_id)
            if case.id in by_case:
                raise ToolError(f"case {given_id!r} is answered more than once")
            by_case[case.id] = answer
        if len(by_case) != len(ALL_CASES):
            raise ToolError(
                f"a submission must answer all {len(ALL_CASES)} cases; "
                f"{len(ALL_CASES) - len(by_case)} have no answer"
            )
        results = [grade(c, by_case[c.id]) for c in ALL_CASES if c.id in by_case]
        return R.submission_document(results, len(ALL_CASES))

    if dev:

        @server.tool()
        def grade_answer(
            case_id: str,
            text: str,
            citations: list[str] | None = None,
            abstained: bool = False,
            retrieved_ids: list[str] | None = None,
        ) -> dict[str, Any]:
            """DEV ONLY. Grade one answer and return its gates, scores and
            notes. This names the failed gate and the documents involved, so
            repeated calls recover the answer key: any score obtained with
            this tool available means nothing. For debugging cases."""
            try:
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
            except R.UsageError as exc:
                raise ToolError(str(exc)) from None
            return R.result_dict(grade(find(case_id), answer))

    return server


def main() -> None:
    build_server().run("stdio")


if __name__ == "__main__":
    main()
