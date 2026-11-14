"""Machine-readable output: the documents the CLI and the MCP server emit.

Every document has a "kind", a "schema_version", the grader and dataset
versions and the canary, and validates against schemas/output.schema.json.

There are two views of a case. The public view is what an agent under test
may see: an opaque id, the tier, the question, the documents and the budget.
It leaves out the failure mode, the descriptive case id (which names the
mode, as in "unanswerable-easy"), the gates and the gold ids, because each
of those says something about the right answer. The dev view adds the
descriptive id and the mode, for the person writing or debugging cases.
"""
from __future__ import annotations

import hashlib
import json
from importlib import resources

from . import stats
from .failure_modes import DATASET_VERSION
from .provenance import CANARY, GRADER_VERSION
from .runner import (
    DIFFICULTY_ORDER,
    gate_breakdown,
    refusal_summary,
    summary_by_mode,
)
from .types import Answer, EvalCase, EvalResult

# Bump when a field is removed or changes meaning. Adding a field does not
# bump it.
SCHEMA_VERSION = "2"

_ANSWER_KEYS = {"case_id", "text", "citations", "abstained", "retrieved_ids"}


class UsageError(ValueError):
    """The caller's input is wrong: bad file, unknown case, malformed answer."""


def load_schema() -> dict:
    path = resources.files(__package__).joinpath("schemas/output.schema.json")
    return json.loads(path.read_text())


def _envelope(kind: str) -> dict:
    return {
        "kind": kind,
        "schema_version": SCHEMA_VERSION,
        "grader_version": GRADER_VERSION,
        "dataset_version": DATASET_VERSION,
        "canary": CANARY,
    }


def public_id(case_id: str) -> str:
    """The opaque id a case goes by in the public view: a stable hash of its
    descriptive id. It is opaque to an agent that sees only tool output; anyone
    holding this repository can recompute it."""
    return "c-" + hashlib.sha256(f"hard-rag-evals/case/{case_id}".encode()).hexdigest()[:12]


def resolve_case(any_id: str, cases: list[EvalCase], allow_descriptive: bool = True) -> EvalCase:
    """The case with this public id, or, when allowed, this descriptive id."""
    for case in cases:
        if public_id(case.id) == any_id or (allow_descriptive and case.id == any_id):
            return case
    raise UsageError(f"unknown case {any_id!r}; see `hard-rag-evals list`")


def public_order(cases: list[EvalCase]) -> list[EvalCase]:
    """Cases sorted by public id. The suite's own order groups cases by tier
    and failure mode, so a position in it would say which mode a case is."""
    return sorted(cases, key=lambda c: public_id(c.id))


def case_summary(case: EvalCase, dev: bool = False) -> dict:
    out = {
        "id": public_id(case.id),
        "difficulty": case.difficulty,
        "query": case.query,
        "n_documents": len(case.corpus.documents),
        "budget": {"max_docs": case.budget.max_docs, "max_chars": case.budget.max_chars},
    }
    if dev:
        out["case_id"] = case.id
        out["mode"] = case.mode
    return out


def public_case(case: EvalCase, dev: bool = False) -> dict:
    """The task as an agent under test may see it: no mode, no descriptive
    id, no gates, no gold ids. dev adds the descriptive id and the mode."""
    out = case_summary(case, dev)
    out["documents"] = [
        {"id": d.id, "text": d.text, "source": d.source, "published": d.published}
        for d in case.corpus.documents
    ]
    return out


def case_list_document(cases: list[EvalCase], dev: bool = False) -> dict:
    ordered = cases if dev else public_order(cases)
    return {**_envelope("case_list"), "cases": [case_summary(c, dev) for c in ordered]}


def case_document(case: EvalCase, dev: bool = False, shuffle_seed: int | None = None) -> dict:
    """case is the case as presented, already shuffled or not; shuffle_seed
    records which: the seed, or None for fixture order."""
    return {**_envelope("case"), "shuffle_seed": shuffle_seed, "case": public_case(case, dev)}


def submission_document(results: list[EvalResult], total_cases: int) -> dict:
    """Aggregate counts for a whole submission and nothing about any one case:
    how many passed overall and per tier. Only a submission that answers
    every case is graded, so no count covers fewer than a whole tier."""
    if len(results) != total_cases:
        raise UsageError(f"a submission must answer all {total_cases} cases")
    by_tier = {}
    for tier in DIFFICULTY_ORDER:
        rows = [r for r in results if r.difficulty == tier]
        if rows:
            by_tier[tier] = stats.pass_rate(rows)
    return {
        **_envelope("submission"),
        "graded": len(results),
        "total_cases": total_cases,
        "summary": stats.pass_rate(results),
        "by_tier": by_tier,
    }


def error_document(message: str, code: str = "usage") -> dict:
    """code is "usage" for the caller's mistake, "internal" for a bug here."""
    return {**_envelope("error"), "error": {"code": code, "message": message}}


def result_dict(result: EvalResult) -> dict:
    return {
        "case_id": result.case_id,
        "public_id": public_id(result.case_id),
        "mode": result.mode,
        "difficulty": result.difficulty,
        "passed": result.passed,
        "gates": dict(result.gates),
        "failed_gates": result.failed_gates,
        "scores": dict(result.scores),
        "notes": list(result.notes),
        "abstained": result.abstained,
        "should_abstain": result.should_abstain,
        "grader_version": result.grader_version,
        "dataset_version": result.dataset_version,
        "shuffle_seed": result.shuffle_seed,
    }


def report_document(agent: str, results: list[EvalResult], config: dict) -> dict:
    """One run, graded. Raises UsageError when there is nothing to report."""
    if not results:
        raise UsageError("no cases were graded")
    by_tier = {}
    for tier in DIFFICULTY_ORDER:
        rows = [r for r in results if r.difficulty == tier]
        if rows:
            by_tier[tier] = stats.pass_rate(rows)
    summary = {
        **stats.pass_rate(results),
        "by_tier": by_tier,
        "by_mode": summary_by_mode(results),
        "gates": {
            gate: {"failed": failed, "applicable": applicable}
            for gate, (failed, applicable) in gate_breakdown(results).items()
        },
        **refusal_summary(results),
    }
    return {
        **_envelope("report"),
        "agent": agent,
        "config": config,
        "summary": summary,
        "results": [result_dict(r) for r in results],
    }


def parse_answer(obj: object, where: str) -> tuple[str, Answer]:
    """One submitted answer, checked field by field. Unknown keys are an
    error: a misspelled "citation" must not grade as an answer citing nothing."""
    if not isinstance(obj, dict):
        raise UsageError(f"{where}: expected a JSON object")
    unknown = sorted(set(obj) - _ANSWER_KEYS)
    if unknown:
        raise UsageError(f"{where}: unknown keys {unknown}; allowed: {sorted(_ANSWER_KEYS)}")
    for key in ("case_id", "text"):
        if not isinstance(obj.get(key), str):
            raise UsageError(f"{where}: {key!r} is required and must be a string")
    for key in ("citations", "retrieved_ids"):
        value = obj.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise UsageError(f"{where}: {key!r} must be a list of strings")
    if not isinstance(obj.get("abstained", False), bool):
        raise UsageError(f"{where}: 'abstained' must be true or false")
    try:
        json.dumps(obj, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError:
        raise UsageError(f"{where}: text holds a character that is not valid Unicode") from None
    return obj["case_id"], Answer(
        text=obj["text"],
        citations=list(obj.get("citations", [])),
        retrieved_ids=list(obj.get("retrieved_ids", [])),
        abstained=obj.get("abstained", False),
    )


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    keys = [k for k, _ in pairs]
    repeated = sorted({k for k in keys if keys.count(k) > 1})
    if repeated:
        raise UsageError(f"keys given more than once in one object: {repeated}")
    return dict(pairs)


def decode_utf8(raw: bytes, source: str) -> str:
    """Input bytes as text, strict UTF-8, the same for a file and for stdin."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UsageError(f"{source}: not valid UTF-8 ({exc.reason} at byte {exc.start})") from None


def _loads_answer_line(line: str, where: str) -> object:
    """One line as JSON, with every way a hostile line can go wrong turned
    into a usage error: bad syntax, nesting deep enough to exhaust the stack,
    an integer too long to convert, a key repeated inside one object (which
    json would resolve silently to the last value), and text that is not
    valid Unicode and so could not be written back out."""
    try:
        obj = json.loads(line, object_pairs_hook=_no_duplicate_keys)
        json.dumps(obj, ensure_ascii=False).encode("utf-8")
    except UsageError as exc:
        raise UsageError(f"{where}: {exc}") from None
    except json.JSONDecodeError as exc:
        raise UsageError(f"{where}: not valid JSON ({exc.msg})") from None
    except RecursionError:
        raise UsageError(f"{where}: JSON nested too deeply") from None
    except UnicodeEncodeError:
        raise UsageError(f"{where}: text holds a character that is not valid Unicode") from None
    except ValueError as exc:
        raise UsageError(f"{where}: not valid JSON ({exc})") from None
    return obj


def parse_answers_jsonl(text: str, source: str = "answers") -> dict[str, Answer]:
    """Answers keyed by case id, from JSON Lines text. Blank lines are skipped.
    A case answered twice is an error, not a last-one-wins."""
    answers: dict[str, Answer] = {}
    for number, line in enumerate(text.split("\n"), start=1):
        if not line.strip():
            continue
        where = f"{source} line {number}"
        obj = _loads_answer_line(line, where)
        case_id, answer = parse_answer(obj, where)
        if case_id in answers:
            raise UsageError(f"{where}: case {case_id!r} is answered more than once")
        answers[case_id] = answer
    return answers
