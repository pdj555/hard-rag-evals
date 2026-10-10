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

    if not notes:
        notes.append("all checks passed")

    return EvalResult(
        case_id=case.id, mode=case.mode, passed=passed, scores=scores, notes=notes
    )


def run_suite(agent: Agent) -> list[EvalResult]:
    return [grade(case, agent.answer(case.query, case.corpus, case.budget)) for case in ALL_CASES]


def render_markdown(agent_name: str, results: list[EvalResult]) -> str:
    lines = [
        f"# Eval report: {agent_name}",
        "",
        "| case | mode | pass | cit_prec | cit_rec | ret_rec | faithful | notes |",
        "| ---- | ---- | ---- | -------- | ------- | ------- | -------- | ----- |",
    ]
    for r in results:
        s = r.scores
        lines.append(
            f"| {r.case_id} | {r.mode} | {'yes' if r.passed else 'no'} "
            f"| {s['citation_precision']:.2f} | {s['citation_recall']:.2f} "
            f"| {s['retrieval_recall']:.2f} | {s['faithfulness']:.2f} "
            f"| {'; '.join(r.notes)} |"
        )
    passed = sum(1 for r in results if r.passed)
    lines += ["", f"**{passed}/{len(results)} cases passed.**"]
    return "\n".join(lines) + "\n"
