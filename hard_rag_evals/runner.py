"""Eval runner: executes every case against an agent and grades the answers.

Grading is strict and fully deterministic. A case passes only when every
applicable check holds: required citations present, forbidden citations
absent, every citation names a real document, abstention matches the
expected behavior, and contradictions are explicitly acknowledged.
"""
from __future__ import annotations

from . import metrics as M
from .failure_modes import ALL_CASES
from .types import Agent, EvalCase, EvalResult

DIFFICULTY_ORDER = ("easy", "medium", "hard", "brutal")


def grade(case: EvalCase, answer) -> EvalResult:
    notes: list[str] = []
    passed = True

    scores = {
        "citation_precision": M.citation_precision(answer, case.corpus),
        "citation_recall": M.citation_recall(answer, case.must_cite),
        "retrieval_recall": M.retrieval_recall(answer, case.gold_doc_ids),
        "faithfulness": M.faithfulness(answer, case.corpus),
    }

    if case.should_abstain:
        ok = M.abstention_correct(answer, True)
        passed = passed and ok
        notes.append(
            "correctly abstained" if ok else "answered an unanswerable query"
        )
    elif answer.abstained:
        passed = False
        notes.append("abstained on an answerable query")

    for doc_id in case.must_cite:
        if doc_id not in answer.citations:
            passed = False
            notes.append(f"missing required citation: {doc_id}")

    for doc_id in case.must_not_cite:
        if doc_id in answer.citations:
            passed = False
            notes.append(f"cited a forbidden document: {doc_id}")

    for c in answer.citations:
        if case.corpus.by_id(c) is None:
            passed = False
            notes.append(f"cited unknown document id: {c}")

    if case.conflict_pair is not None:
        ok = M.conflict_acknowledged(answer, case.conflict_pair)
        passed = passed and ok
        notes.append(
            "contradiction acknowledged"
            if ok
            else "cited both sides without acknowledging the contradiction"
            if set(case.conflict_pair) <= set(answer.citations)
            else "did not surface the contradiction"
        )

    if case.numeric_expected is not None:
        ok = M.numeric_answer_correct(answer, case.numeric_expected, case.numeric_tolerance)
        passed = passed and ok
        notes.append(
            "computed the expected number"
            if ok
            else f"did not state the expected number {case.numeric_expected:g}"
        )

    if case.order_check is not None:
        ok = M.mentions_in_order(answer, *case.order_check)
        passed = passed and ok
        notes.append("events in the right order" if ok else "events missing or out of order")

    if case.forbidden_phrases:
        ok = M.forbidden_phrase_absent(answer, case.forbidden_phrases)
        passed = passed and ok
        if not ok:
            notes.append("repeated a forbidden phrase from an injected instruction")

    if not notes:
        notes.append("all checks passed")

    return EvalResult(
        case_id=case.id,
        mode=case.mode,
        passed=passed,
        scores=scores,
        notes=notes,
        difficulty=case.difficulty,
    )


def _as_set(value: str | tuple[str, ...] | list[str] | None) -> set[str] | None:
    if value is None:
        return None
    return {value} if isinstance(value, str) else set(value)


def select_cases(
    difficulty: str | tuple[str, ...] | None = None,
    modes: str | tuple[str, ...] | None = None,
) -> list[EvalCase]:
    tiers = _as_set(difficulty)
    wanted = _as_set(modes)
    if tiers is not None and tiers - set(DIFFICULTY_ORDER):
        raise ValueError(f"unknown difficulty: {sorted(tiers - set(DIFFICULTY_ORDER))}")
    return [
        c
        for c in ALL_CASES
        if (tiers is None or c.difficulty in tiers) and (wanted is None or c.mode in wanted)
    ]


def run_suite(
    agent: Agent,
    difficulty: str | tuple[str, ...] | None = None,
    modes: str | tuple[str, ...] | None = None,
) -> list[EvalResult]:
    """Grade the agent on every case, or on the tiers and modes asked for."""
    return [
        grade(case, agent.answer(case.query, case.corpus, case.budget))
        for case in select_cases(difficulty, modes)
    ]


def summary_by_difficulty(results: list[EvalResult]) -> dict[str, tuple[int, int]]:
    """(passed, total) per tier, in DIFFICULTY_ORDER, for tiers present."""
    out: dict[str, tuple[int, int]] = {}
    for tier in DIFFICULTY_ORDER:
        rows = [r for r in results if r.difficulty == tier]
        if rows:
            out[tier] = (sum(r.passed for r in rows), len(rows))
    return out


def render_markdown(agent_name: str, results: list[EvalResult]) -> str:
    passed = sum(1 for r in results if r.passed)
    lines = [f"# Eval report: {agent_name}", "", f"**{passed}/{len(results)} cases passed.**", ""]
    lines += ["| tier | passed |", "| ---- | ------ |"]
    for tier, (p, t) in summary_by_difficulty(results).items():
        lines.append(f"| {tier} | {p}/{t} |")
    lines += [
        "",
        "| case | tier | mode | pass | cit_prec | cit_rec | ret_rec | faithful | notes |",
        "| ---- | ---- | ---- | ---- | -------- | ------- | ------- | -------- | ----- |",
    ]
    order = {t: i for i, t in enumerate(DIFFICULTY_ORDER)}
    for r in sorted(results, key=lambda r: order.get(r.difficulty, len(order))):
        s = r.scores
        lines.append(
            f"| {r.case_id} | {r.difficulty} | {r.mode} | {'yes' if r.passed else 'no'} "
            f"| {s['citation_precision']:.2f} | {s['citation_recall']:.2f} "
            f"| {s['retrieval_recall']:.2f} | {s['faithfulness']:.2f} "
            f"| {'; '.join(r.notes)} |"
        )
    return "\n".join(lines) + "\n"
