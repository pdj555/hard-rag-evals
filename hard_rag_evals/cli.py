"""Command line entry point: hard-rag-evals.

    hard-rag-evals list                      the cases
    hard-rag-evals show CASE_ID              one case: question, documents, budget
    hard-rag-evals run --agent NAME          run a built-in agent and grade it
    hard-rag-evals grade ANSWERS.jsonl       grade answers written by any agent
    hard-rag-evals schema                    the JSON Schema of --json output
    hard-rag-evals mcp                       serve the suite over MCP on stdio

With --json each command prints exactly one JSON document on stdout that
validates against the schema. Exit codes:

    0  the command worked, and every graded case passed
    1  the command worked, and at least one graded case failed
    2  usage error: bad arguments, unknown case, malformed answers file
    3  internal error: a bug in this package
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from . import report as R
from .failure_modes import ALL_CASES
from .gamers import GAMERS
from .reference_agent import ReferenceAgent
from .runner import (
    DIFFICULTY_ORDER,
    grade,
    permute_documents,
    render_markdown,
    run_suite,
    select_cases,
)

EXIT_OK = 0
EXIT_CASES_FAILED = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3

AGENTS = {"reference": ReferenceAgent, **{g.name: g for g in GAMERS}}
MODES = tuple(dict.fromkeys(c.mode for c in ALL_CASES))


class _Parser(argparse.ArgumentParser):
    """argparse exits 2 on a bad command line already. With --json on the
    command line the error also goes to stdout as a document, so a caller
    that only parses stdout still learns what went wrong."""

    argv: list[str] = []

    def error(self, message: str):
        if "--json" in _Parser.argv:
            print(json.dumps(R.error_document(message)))
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="hard-rag-evals",
        description="Deterministic failure mode evals for agents that answer from documents.",
        epilog="Exit codes: 0 ok and all cases passed, 1 some cases failed, "
        "2 usage error, 3 internal error.",
    )
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    def add_filters(p):
        p.add_argument("--difficulty", action="append", choices=DIFFICULTY_ORDER,
                       help="keep only this tier; repeat for several")
        p.add_argument("--mode", action="append", choices=MODES,
                       help="keep only this failure mode; repeat for several")

    def add_json(p):
        p.add_argument("--json", action="store_true",
                       help="print one JSON document that validates against the schema")

    p = sub.add_parser("list", help="list the cases")
    add_filters(p)
    add_json(p)

    p = sub.add_parser("show", help="one case as an agent sees it: question, documents, budget")
    p.add_argument("case_id")
    p.add_argument("--shuffle-seed", type=int, default=None,
                   help="permute the documents with this seed")
    add_json(p)

    p = sub.add_parser("run", help="run a built-in agent on the suite and grade it")
    p.add_argument("--agent", required=True, choices=sorted(AGENTS))
    add_filters(p)
    p.add_argument("--shuffle-seed", type=int, default=None,
                   help="permute each case's documents with this seed before the agent sees them")
    add_json(p)

    p = sub.add_parser(
        "grade",
        help="grade an answers file: JSON Lines, one object per case with case_id, text, "
        "and optionally citations, abstained, retrieved_ids",
    )
    p.add_argument("answers", help="path to the JSON Lines file, or - for stdin")
    p.add_argument("--agent-name", default="external",
                   help="the name to put on the report (default: external)")
    p.add_argument("--allow-partial", action="store_true",
                   help="grade only the cases answered; without it a missing case is a usage error")
    add_json(p)

    sub.add_parser("schema", help="print the JSON Schema that --json output validates against")
    sub.add_parser("mcp", help="serve the suite over MCP on stdio (needs the mcp extra)")
    return parser


def _emit_report(document: dict, results, as_json: bool) -> int:
    if as_json:
        print(json.dumps(document))
    else:
        sys.stdout.write(render_markdown(document["agent"], results))
    return EXIT_OK if all(r.passed for r in results) else EXIT_CASES_FAILED


def _cmd_list(args) -> int:
    cases = select_cases(tuple(args.difficulty) if args.difficulty else None,
                         tuple(args.mode) if args.mode else None)
    if args.json:
        print(json.dumps(R.case_list_document(cases)))
    else:
        for c in cases:
            print(f"{c.id}\t{c.difficulty}\t{c.mode}\t{len(c.corpus.documents)} docs\t{c.query}")
    return EXIT_OK


def _cmd_show(args) -> int:
    case = next((c for c in ALL_CASES if c.id == args.case_id), None)
    if case is None:
        raise R.UsageError(f"unknown case {args.case_id!r}; see `hard-rag-evals list`")
    if args.shuffle_seed is not None:
        case = permute_documents(case, args.shuffle_seed)
    if args.json:
        print(json.dumps(R.case_document(case)))
    else:
        print(f"{case.id} ({case.difficulty}, {case.mode})")
        print(f"budget: {case.budget.max_docs} documents, {case.budget.max_chars} characters")
        print(f"question: {case.query}")
        for d in case.corpus.documents:
            print(f"\n[{d.id}] {d.source}, {d.published}\n{d.text}")
    return EXIT_OK


def _cmd_run(args) -> int:
    agent = AGENTS[args.agent]()
    results = run_suite(
        agent,
        tuple(args.difficulty) if args.difficulty else None,
        tuple(args.mode) if args.mode else None,
        shuffle_seed=args.shuffle_seed,
    )
    config = {
        "source": "built_in_agent",
        "difficulty": args.difficulty,
        "modes": args.mode,
        "shuffle_seed": args.shuffle_seed,
        "missing_case_ids": [],
    }
    return _emit_report(R.report_document(agent.name, results, config), results, args.json)


def grade_answers(answers: dict, allow_partial: bool = False):
    """Grade answers keyed by case id against the suite. Returns the results
    in suite order and the ids of cases left unanswered."""
    cases = {c.id: c for c in ALL_CASES}
    unknown = sorted(set(answers) - set(cases))
    if unknown:
        raise R.UsageError(f"unknown case ids: {unknown}; see `hard-rag-evals list`")
    missing = [cid for cid in cases if cid not in answers]
    if missing and not allow_partial:
        raise R.UsageError(
            f"{len(missing)} of {len(cases)} cases have no answer: {missing}. "
            "Answer every case, or pass --allow-partial to grade only those answered."
        )
    results = [grade(cases[cid], answers[cid]) for cid in cases if cid in answers]
    return results, missing


def _cmd_grade(args) -> int:
    if args.answers == "-":
        text, source = sys.stdin.read(), "stdin"
    else:
        path = Path(args.answers)
        try:
            text, source = path.read_text(encoding="utf-8"), path.name
        except (OSError, UnicodeDecodeError) as exc:
            raise R.UsageError(f"cannot read {args.answers}: {exc}") from None
    answers = R.parse_answers_jsonl(text, source)
    results, missing = grade_answers(answers, args.allow_partial)
    config = {
        "source": "answers_file",
        "difficulty": None,
        "modes": None,
        "shuffle_seed": None,
        "missing_case_ids": missing,
    }
    return _emit_report(R.report_document(args.agent_name, results, config), results, args.json)


def _cmd_schema(args) -> int:
    print(json.dumps(R.load_schema(), indent=2))
    return EXIT_OK


def _cmd_mcp(args) -> int:
    try:
        from .mcp_server import build_server
    except ImportError as exc:
        raise R.UsageError(
            f"the MCP server needs the mcp extra: pip install 'hard-rag-evals[mcp]' ({exc})"
        ) from None
    build_server().run("stdio")
    return EXIT_OK


_COMMANDS = {
    "list": _cmd_list,
    "show": _cmd_show,
    "run": _cmd_run,
    "grade": _cmd_grade,
    "schema": _cmd_schema,
    "mcp": _cmd_mcp,
}


def main(argv: list[str] | None = None) -> int:
    _Parser.argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    as_json = getattr(args, "json", False)
    try:
        return _COMMANDS[args.command](args)
    except R.UsageError as exc:
        if as_json:
            print(json.dumps(R.error_document(str(exc))))
        print(f"hard-rag-evals: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except Exception:  # a bug here must not look like "some cases failed"
        traceback.print_exc()
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
