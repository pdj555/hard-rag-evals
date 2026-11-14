"""Machine-readable output: the documents the CLI and the MCP server emit.

Every document has a "kind", a "schema_version", the grader version and the
canary, and validates against schemas/output.schema.json. What an agent under
test is shown about a case (public_case) leaves out the gates and the gold
ids: the question, the documents and the budget are the task, the rest is
the answer key.
"""
from __future__ import annotations

import json
from importlib import resources

from . import stats
from .provenance import CANARY, DATASET_VERSION, GRADER_VERSION
from .runner import (
    DIFFICULTY_ORDER,
    gate_breakdown,
    refusal_summary,
    summary_by_mode,
)
from .types import Answer, EvalCase, EvalResult

# Bump when a field is removed or changes meaning. Adding a field does not
# bump it.
SCHEMA_VERSION = "1"

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


def case_summary(case: EvalCase) -> dict:
    return {
        "id": case.id,
        "mode": case.mode,
        "difficulty": case.difficulty,
        "query": case.query,
        "n_documents": len(case.corpus.documents),
        "budget": {"max_docs": case.budget.max_docs, "max_chars": case.budget.max_chars},
    }


def public_case(case: EvalCase) -> dict:
    """The task as an agent under test may see it: no gates, no gold ids."""
    out = case_summary(case)
    out["documents"] = [
        {"id": d.id, "text": d.text, "source": d.source, "published": d.published}
        for d in case.corpus.documents
    ]
    return out


def case_list_document(cases: list[EvalCase]) -> dict:
    return {**_envelope("case_list"), "cases": [case_summary(c) for c in cases]}


def case_document(case: EvalCase) -> dict:
    return {**_envelope("case"), "case": public_case(case)}


def error_document(message: str) -> dict:
    return {**_envelope("error"), "error": {"code": "usage", "message": message}}


def result_dict(result: EvalResult) -> dict:
    return {
        "case_id": result.case_id,
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
    return obj["case_id"], Answer(
        text=obj["text"],
        citations=list(obj.get("citations", [])),
        retrieved_ids=list(obj.get("retrieved_ids", [])),
        abstained=obj.get("abstained", False),
    )


def parse_answers_jsonl(text: str, source: str = "answers") -> dict[str, Answer]:
    """Answers keyed by case id, from JSON Lines text. Blank lines are skipped.
    A case answered twice is an error, not a last-one-wins."""
    answers: dict[str, Answer] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        where = f"{source} line {number}"
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise UsageError(f"{where}: not valid JSON ({exc.msg})") from None
        case_id, answer = parse_answer(obj, where)
        if case_id in answers:
            raise UsageError(f"{where}: case {case_id!r} is answered more than once")
        answers[case_id] = answer
    return answers
