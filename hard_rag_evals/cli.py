"""Command line entry point: hard-rag-evals.

    hard-rag-evals list                      the cases, public view
    hard-rag-evals show ID                   one case: question, documents, budget
    hard-rag-evals run --agent NAME          run a built-in agent and grade it
    hard-rag-evals grade ANSWERS.jsonl       grade answers written by any agent
    hard-rag-evals schema                    the JSON Schema of --json output
    hard-rag-evals mcp                       serve the suite over MCP on stdio

list and show print the public view: opaque case ids, no failure mode. Pass
--dev to see descriptive ids and modes. run and grade are for the person
running the eval: their reports name every case and every failed gate, so an
agent under test must not be the one reading them.

With --json each command prints exactly one JSON document on stdout that
validates against the schema. Exit codes:

    0  the command worked, and every graded case passed
    1  the command worked, and at least one graded case failed
    2  usage error: bad arguments, unknown case, malformed answers file
    3  internal error: a bug in this package

If stdout is closed before the output is written (a pipe into `head`), the
command exits quietly with the code it would have returned.
"""
from __future__ import annotations

import argparse
import json
import os
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
            _write(json.dumps(R.error_document(message)) + "\n")
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

    def add_dev(p):
        p.add_argument("--dev", action="store_true",
                       help="dev view: descriptive case ids and failure modes, which say "
                       "something about the right answer; not for an agent under test")

    p = sub.add_parser("list", help="list the cases (public view: opaque ids, no failure mode)")
    add_filters(p)
    add_dev(p)
    add_json(p)

    p = sub.add_parser("show", help="one case as an agent sees it: question, documents, budget")
    p.add_argument("case_id", help="a public id from `list`; with --dev, a descriptive id too")
    p.add_argument("--shuffle-seed", type=int, default=None,
                   help="permute the documents with this seed")
    add_dev(p)
    add_json(p)

    p = sub.add_parser("run", help="run a built-in agent on the suite and grade it")
    p.add_argument("--agent", required=True, choices=sorted(AGENTS))
    add_filters(p)
    p.add_argument("--shuffle-seed", type=int, default=None,
                   help="permute each case's documents with this seed before the agent sees them")
    add_json(p)

    p = sub.add_parser(
        "grade",
        help="grade an answers file: JSON Lines, one object per case with case_id (public or "
        "descriptive), text, and optionally citations, abstained, retrieved_ids",
    )
    p.add_argument("answers", help="path to the JSON Lines file, or - for stdin")
    p.add_argument("--agent-name", default="external",
                   help="the name to put on the report (default: external)")
    p.add_argument("--allow-partial", action="store_true",
                   help="grade only the cases answered; without it a missing case is a usage error")
    add_json(p)

    sub.add_parser("schema", help="print the JSON Schema that --json output validates against")

    p = sub.add_parser("mcp", help="serve the suite over MCP on stdio (needs the mcp extra)")
    p.add_argument("--dev", action="store_true",
                   help="also offer per-case grading with gates and notes, and descriptive ids. "
                   "This hands the agent the answer key one probe at a time: scores from a "
                   "server started with --dev mean nothing")
    return parser


def _report(document: dict, results, as_json: bool) -> tuple[int, str]:
    code = EXIT_OK if all(r.passed for r in results) else EXIT_CASES_FAILED
    if as_json:
        return code, json.dumps(document) + "\n"
    return code, render_markdown(
        document["agent"], results, missing=document["config"]["missing_case_ids"]
    )


def _cmd_list(args) -> tuple[int, str]:
    if args.mode and not args.dev:
        raise R.UsageError("--mode filters by failure mode, which the public view hides; add --dev")
    cases = select_cases(tuple(args.difficulty) if args.difficulty else None,
                         tuple(args.mode) if args.mode else None)
    document = R.case_list_document(cases, dev=args.dev)
    if args.json:
        return EXIT_OK, json.dumps(document) + "\n"
    lines = []
    for c in document["cases"]:
        dev = f"\t{c['case_id']}\t{c['mode']}" if args.dev else ""
        lines.append(f"{c['id']}{dev}\t{c['difficulty']}\t{c['n_documents']} docs\t{c['query']}")
    return EXIT_OK, "".join(line + "\n" for line in lines)


def _cmd_show(args) -> tuple[int, str]:
    case = R.resolve_case(args.case_id, ALL_CASES, allow_descriptive=args.dev)
    if args.shuffle_seed is not None:
        case = permute_documents(case, args.shuffle_seed)
    document = R.case_document(case, dev=args.dev)
    if args.json:
        return EXIT_OK, json.dumps(document) + "\n"
    c = document["case"]
    dev = f", {c['case_id']}, {c['mode']}" if args.dev else ""
    lines = [
        f"{c['id']} ({c['difficulty']}{dev})",
        f"budget: {c['budget']['max_docs']} documents, {c['budget']['max_chars']} characters",
        f"question: {c['query']}",
    ]
    for d in c["documents"]:
        lines.append(f"\n[{d['id']}] {d['source']}, {d['published']}\n{d['text']}")
    return EXIT_OK, "\n".join(lines) + "\n"


def _cmd_run(args) -> tuple[int, str]:
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
        "total_cases": len(results),
    }
    return _report(R.report_document(agent.name, results, config), results, args.json)


def grade_answers(answers: dict, allow_partial: bool = False, allow_descriptive: bool = True):
    """Grade answers against the suite. Keys are public ids or, when allowed,
    descriptive ids. Returns the results in suite order and the descriptive
    ids of cases left unanswered."""
    by_case: dict = {}
    for given_id, answer in answers.items():
        case = R.resolve_case(given_id, ALL_CASES, allow_descriptive)
        if case.id in by_case:
            raise R.UsageError(f"case {given_id!r} is answered more than once, under two ids")
        by_case[case.id] = answer
    missing = [c.id for c in ALL_CASES if c.id not in by_case]
    if missing and not allow_partial:
        raise R.UsageError(
            f"{len(missing)} of {len(ALL_CASES)} cases have no answer: {missing}. "
            "Answer every case, or pass --allow-partial to grade only those answered."
        )
    results = [grade(c, by_case[c.id]) for c in ALL_CASES if c.id in by_case]
    return results, missing


def _cmd_grade(args) -> tuple[int, str]:
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
        "total_cases": len(ALL_CASES),
    }
    return _report(R.report_document(args.agent_name, results, config), results, args.json)


def _cmd_schema(args) -> tuple[int, str]:
    return EXIT_OK, json.dumps(R.load_schema(), indent=2) + "\n"


def _cmd_mcp(args) -> tuple[int, str]:
    try:
        from .mcp_server import build_server
    except ImportError as exc:
        raise R.UsageError(
            f"the MCP server needs the mcp extra: pip install 'hard-rag-evals[mcp]' ({exc})"
        ) from None
    build_server(dev=args.dev).run("stdio")
    return EXIT_OK, ""


_COMMANDS = {
    "list": _cmd_list,
    "show": _cmd_show,
    "run": _cmd_run,
    "grade": _cmd_grade,
    "schema": _cmd_schema,
    "mcp": _cmd_mcp,
}


def _write(text: str) -> bool:
    """Write to stdout and flush. False when the reader has gone away.

    A closed pipe (`hard-rag-evals list | head -1`) is the reader's choice,
    not an error here. Python would otherwise print a traceback, and again at
    exit when it flushes, so stdout is pointed at the null device before
    returning.
    """
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
        return True
    except BrokenPipeError:
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except (OSError, ValueError, AttributeError):
            pass  # stdout is not a real file descriptor; nothing left to protect
        return False


def main(argv: list[str] | None = None) -> int:
    _Parser.argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    as_json = getattr(args, "json", False)
    try:
        code, text = _COMMANDS[args.command](args)
    except R.UsageError as exc:
        if as_json:
            _write(json.dumps(R.error_document(str(exc))) + "\n")
        print(f"hard-rag-evals: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except Exception as exc:  # a bug here must not look like "some cases failed"
        traceback.print_exc()
        if as_json:
            message = f"internal error: {type(exc).__name__}: {exc}"
            _write(json.dumps(R.error_document(message, code="internal")) + "\n")
        return EXIT_INTERNAL
    _write(text)  # a closed pipe changes nothing about the exit code
    return code


if __name__ == "__main__":
    raise SystemExit(main())
