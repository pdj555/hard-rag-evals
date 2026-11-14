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

show and run present each case's documents shuffled with a fixed published
seed. --shuffle-seed picks another; --fixture-order keeps the order in the
fixture, which usually puts a required document first.

With --json each command prints exactly one JSON document on stdout that
validates against the schema. Exit codes:

    0  the command worked, and every graded case passed
    1  the command worked, and at least one graded case failed
    2  usage error: bad arguments, unknown case, malformed input
    3  internal error (a bug in this package), or the output could not be
       written (disk full, stdout closed or invalid)

One exception: if the reader of a pipe goes away before the output is
written (`hard-rag-evals list | head -1`), the command exits quietly with
the code it would have returned.
"""
from __future__ import annotations

import argparse
import errno
import json
import os
import sys
import traceback
from pathlib import Path

from . import report as R
from .failure_modes import ALL_CASES
from .gamers import GAMERS, Fabricator
from .reference_agent import ReferenceAgent
from .runner import (
    DEFAULT_SHUFFLE_SEED,
    DIFFICULTY_ORDER,
    grade,
    present,
    render_markdown,
    run_suite,
    select_cases,
)

EXIT_OK = 0
EXIT_CASES_FAILED = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3

AGENTS = {
    "reference": ReferenceAgent,
    "fabricating": Fabricator,
    **{g.name: g for g in GAMERS},
}
MODES = tuple(dict.fromkeys(c.mode for c in ALL_CASES))


class OutputError(Exception):
    """stdout could not be written, for a reason other than a reader leaving."""


def _warn(message: str) -> None:
    """A line on stderr. If stderr cannot be written either there is nowhere
    left to say so, and the exit code has to carry it."""
    try:
        print(message, file=sys.stderr)
        sys.stderr.flush()
    except (OSError, ValueError, AttributeError):
        pass


def _silence_stdout() -> None:
    """Point stdout at the null device so the interpreter's flush at exit
    cannot fail a second time, with a traceback and its own exit code."""
    try:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    except (OSError, ValueError, AttributeError):
        pass  # no usable descriptor; nothing left to protect


def _write(text: str) -> bool:
    """Write to stdout and flush. Returns False when the reader of a pipe has
    gone away, which is the reader's choice and not an error. Raises
    OutputError when stdout fails any other way: no space left, a bad or
    closed descriptor. Raises UnicodeEncodeError for text the stream's
    encoding cannot carry; the caller reports that as malformed input."""
    try:
        if sys.stdout is None:  # the process was started with stdout closed
            raise OSError(errno.EBADF, "stdout is closed")
        sys.stdout.write(text)
        sys.stdout.flush()
        return True
    except UnicodeEncodeError:
        raise
    except BrokenPipeError:
        _silence_stdout()
        return False
    except (OSError, ValueError) as exc:  # ValueError: write to a closed file object
        _silence_stdout()
        if isinstance(exc, OSError) and exc.errno == errno.EPIPE:
            return False
        raise OutputError(str(exc)) from None


class _Parser(argparse.ArgumentParser):
    """No abbreviations: --dev must be typed as --dev, so a prefix that
    happens to be unique today cannot change meaning when a flag is added.

    argparse exits 2 on a bad command line already. With --json on the
    command line the error also goes to stdout as a document, so a caller
    that only parses stdout still learns what went wrong."""

    argv: list[str] = []

    def __init__(self, *args, **kwargs):
        kwargs["allow_abbrev"] = False
        super().__init__(*args, **kwargs)

    def error(self, message: str):
        code = EXIT_USAGE
        if "--json" in _Parser.argv:
            try:
                _write(json.dumps(R.error_document(message)) + "\n")
            except OutputError as exc:
                code = EXIT_INTERNAL
                _warn(f"{self.prog}: error: could not write output: {exc}")
        _warn(f"{self.prog}: error: {message}")
        raise SystemExit(code)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="hard-rag-evals",
        description="Deterministic failure mode evals for agents that answer from documents.",
        epilog="Exit codes: 0 ok and all cases passed, 1 some cases failed, "
        "2 usage error, 3 internal error or output could not be written.",
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

    def add_order(p):
        p.add_argument("--shuffle-seed", type=int, default=None,
                       help=f"shuffle each case's documents with this seed "
                       f"(default: {DEFAULT_SHUFFLE_SEED})")
        p.add_argument("--fixture-order", action="store_true",
                       help="keep the documents in the order the fixture lists them. That "
                       "order usually puts a required document first, so it leaks")

    p = sub.add_parser("list", help="list the cases (public view: opaque ids, no failure mode)")
    add_filters(p)
    add_dev(p)
    add_json(p)

    p = sub.add_parser("show", help="one case as an agent sees it: question, documents, budget")
    p.add_argument("case_id", help="a public id from `list`; with --dev, a descriptive id too")
    add_order(p)
    add_dev(p)
    add_json(p)

    p = sub.add_parser("run", help="run a built-in agent on the suite and grade it")
    p.add_argument("--agent", required=True, choices=sorted(AGENTS))
    add_filters(p)
    add_order(p)
    add_json(p)

    p = sub.add_parser(
        "grade",
        help="grade an answers file: JSON Lines in UTF-8, one object per case with case_id "
        "(public or descriptive), text, and optionally citations, abstained, retrieved_ids",
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


def _seed(args) -> int | None:
    if args.fixture_order and args.shuffle_seed is not None:
        raise R.UsageError("--fixture-order and --shuffle-seed cannot be given together")
    if args.fixture_order:
        return None
    return DEFAULT_SHUFFLE_SEED if args.shuffle_seed is None else args.shuffle_seed


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
    seed = _seed(args)
    case = present(R.resolve_case(args.case_id, ALL_CASES, allow_descriptive=args.dev), seed)
    document = R.case_document(case, dev=args.dev, shuffle_seed=seed)
    if args.json:
        return EXIT_OK, json.dumps(document) + "\n"
    c = document["case"]
    dev = f", {c['case_id']}, {c['mode']}" if args.dev else ""
    order = "fixture order" if seed is None else f"shuffled with seed {seed}"
    lines = [
        f"{c['id']} ({c['difficulty']}{dev})",
        f"budget: {c['budget']['max_docs']} documents, {c['budget']['max_chars']} characters",
        f"documents: {order}",
        f"question: {c['query']}",
    ]
    for d in c["documents"]:
        lines.append(f"\n[{d['id']}] {d['source']}, {d['published']}\n{d['text']}")
    return EXIT_OK, "\n".join(lines) + "\n"


def _cmd_run(args) -> tuple[int, str]:
    seed = _seed(args)
    agent = AGENTS[args.agent]()
    results = run_suite(
        agent,
        tuple(args.difficulty) if args.difficulty else None,
        tuple(args.mode) if args.mode else None,
        shuffle_seed=seed,
    )
    config = {
        "source": "built_in_agent",
        "difficulty": args.difficulty,
        "modes": args.mode,
        "shuffle_seed": seed,
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


def _read_answers(arg: str) -> tuple[str, str]:
    """The answers file as text and a name for error messages. A file and
    stdin are read as bytes and decoded the same way, strict UTF-8, so the
    same bytes never grade differently depending on how they arrived."""
    try:
        if arg == "-":
            raw, source = sys.stdin.buffer.read(), "stdin"
        else:
            raw, source = Path(arg).read_bytes(), Path(arg).name
    except (OSError, ValueError, AttributeError) as exc:
        raise R.UsageError(f"cannot read {arg}: {exc}") from None
    return R.decode_utf8(raw, source), source


def _cmd_grade(args) -> tuple[int, str]:
    text, source = _read_answers(args.answers)
    answers = R.parse_answers_jsonl(text, source)
    results, missing = grade_answers(answers, args.allow_partial)
    config = {
        "source": "answers_file",
        "difficulty": None,
        "modes": None,
        "shuffle_seed": "n/a",
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


def _usage_error(message: str, as_json: bool) -> int:
    code = EXIT_USAGE
    if as_json:
        try:
            _write(json.dumps(R.error_document(message)) + "\n")
        except OutputError as exc:
            code = EXIT_INTERNAL
            _warn(f"hard-rag-evals: error: could not write output: {exc}")
    _warn(f"hard-rag-evals: error: {message}")
    return code


def main(argv: list[str] | None = None) -> int:
    _Parser.argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    as_json = getattr(args, "json", False)
    try:
        code, text = _COMMANDS[args.command](args)
        _write(text)  # a reader that left changes nothing about the exit code
        return code
    except R.UsageError as exc:
        return _usage_error(str(exc), as_json)
    except UnicodeEncodeError:
        # Only text taken from the input reaches the output unescaped.
        return _usage_error(
            "the input holds text that cannot be written in the output encoding", as_json
        )
    except RecursionError:
        return _usage_error("the input is nested too deeply to process", as_json)
    except OutputError as exc:
        _warn(f"hard-rag-evals: error: could not write output: {exc}")
        return EXIT_INTERNAL
    except Exception as exc:  # a bug here must not look like "some cases failed"
        try:
            traceback.print_exc()
        except (OSError, ValueError, AttributeError):
            pass
        if as_json:
            message = f"internal error: {type(exc).__name__}: {exc}"
            try:
                _write(json.dumps(R.error_document(message, code="internal")) + "\n")
            except (OutputError, UnicodeEncodeError):
                pass
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
