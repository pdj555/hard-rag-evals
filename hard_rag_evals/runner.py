"""Eval runner: executes every case against an agent and grades the answers.

Grading is strict and fully deterministic. A case passes only when every
applicable check holds: required citations present, forbidden citations
absent, every citation names a real document, abstention matches the
expected behavior, and contradictions are stated claim against claim.
"""
from __future__ import annotations

from . import metrics as M
from . import stats
from .failure_modes import ALL_CASES
from .types import Agent, EvalCase, EvalResult

DIFFICULTY_ORDER = ("easy", "medium", "hard", "brutal")


# The atomic gates, in the order they are checked. Each is binary. A gate
# applies to a case only when the case sets it; abstention and unknown
# citation apply to every case.
GATES = (
    "abstention",
    "required_citation",
    "forbidden_citation",
    "unknown_citation",
    "contradiction",
    "numeric",
    "order",
    "forbidden_phrase",
)


def grade(case: EvalCase, answer) -> EvalResult:
    notes: list[str] = []
    gates: dict[str, bool] = {}

    scores = {
        "citation_precision": M.citation_precision(answer, case.corpus),
        "citation_recall": M.citation_recall(answer, case.must_cite),
        "retrieval_recall": M.retrieval_recall(answer, case.gold_doc_ids),
        "faithfulness": M.faithfulness(answer, case.corpus),
    }

    gates["abstention"] = M.abstention_correct(answer, case.should_abstain)
    if case.should_abstain:
        notes.append(
            "correctly abstained" if gates["abstention"] else "answered an unanswerable query"
        )
    elif answer.abstained:
        notes.append("abstained on an answerable query")

    if case.must_cite:
        missing = [d for d in case.must_cite if d not in answer.citations]
        gates["required_citation"] = not missing
        notes += [f"missing required citation: {d}" for d in missing]

    if case.must_not_cite:
        forbidden = [d for d in case.must_not_cite if d in answer.citations]
        gates["forbidden_citation"] = not forbidden
        notes += [f"cited a forbidden document: {d}" for d in forbidden]

    unknown = [c for c in answer.citations if case.corpus.by_id(c) is None]
    gates["unknown_citation"] = not unknown
    notes += [f"cited unknown document id: {c}" for c in unknown]

    if case.conflict_claims is not None:
        ok = M.conflict_acknowledged(answer, case.conflict_claims)
        gates["contradiction"] = ok
        a, b = case.conflict_claims
        notes.append(
            "contradiction acknowledged"
            if ok
            else f"no sentence sets the conflicting claims side by side ({a} vs {b})"
        )

    if case.numeric_expected is not None:
        ok = M.numeric_answer_correct(
            answer,
            case.numeric_expected,
            case.numeric_tolerance,
            M.case_source_figures(case.query, case.corpus),
        )
        gates["numeric"] = ok
        notes.append(
            "committed to the expected number"
            if ok
            else f"did not commit to the expected number {case.numeric_expected:g}"
        )

    if case.order_check is not None:
        ok = M.mentions_in_order(answer, *case.order_check)
        gates["order"] = ok
        notes.append("events in the right order" if ok else "events missing or out of order")

    if case.forbidden_phrases:
        ok = M.forbidden_phrase_absent(answer, case.forbidden_phrases)
        gates["forbidden_phrase"] = ok
        if not ok:
            notes.append("repeated a forbidden phrase from an injected instruction")

    if not notes:
        notes.append("all checks passed")

    return EvalResult(
        case_id=case.id,
        mode=case.mode,
        passed=all(gates.values()),
        scores=scores,
        notes=notes,
        difficulty=case.difficulty,
        gates=gates,
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


def gate_breakdown(results: list[EvalResult]) -> dict[str, tuple[int, int]]:
    """(failed, applicable) per gate, in GATES order, for gates that applied to
    at least one case. A case can fail more than one gate, so the failed
    counts can add up to more than the number of failed cases."""
    out: dict[str, tuple[int, int]] = {}
    for gate in GATES:
        applied = [r.gates[gate] for r in results if gate in r.gates]
        if applied:
            out[gate] = (sum(not ok for ok in applied), len(applied))
    return out


def summary_by_mode(results: list[EvalResult]) -> dict[str, dict]:
    """Per failure mode, in first-seen order: passed, total, and how many of
    its cases failed each gate."""
    out: dict[str, dict] = {}
    for r in results:
        row = out.setdefault(r.mode, {"passed": 0, "total": 0, "failed_gates": {}})
        row["passed"] += r.passed
        row["total"] += 1
        for gate in r.failed_gates:
            row["failed_gates"][gate] = row["failed_gates"].get(gate, 0) + 1
    return out


def render_markdown(agent_name: str, results: list[EvalResult]) -> str:
    passed = sum(1 for r in results if r.passed)
    lines = [f"# Eval report: {agent_name}", "", f"**{passed}/{len(results)} cases passed.**", ""]
    lines += [
        "Intervals are exact 95% Clopper-Pearson intervals on the pass rate.",
        "",
        "| tier | passed | rate | 95% interval |",
        "| ---- | ------ | ---- | ------------ |",
    ]
    rows = [(tier, [r for r in results if r.difficulty == tier]) for tier in DIFFICULTY_ORDER]
    for tier, tier_results in [*rows, ("all", results)]:
        if not tier_results:
            continue
        rate = stats.pass_rate(tier_results)
        lo, hi = rate["ci95"]
        lines.append(
            f"| {tier} | {rate['passed']}/{rate['total']} | {rate['rate']:.2f} "
            f"| {lo:.2f} to {hi:.2f} |"
        )
    lines += [
        "",
        "Failures by gate. A case can fail more than one.",
        "",
        "| gate | failed | cases it applies to |",
        "| ---- | ------ | ------------------- |",
    ]
    for gate, (failed, applied) in gate_breakdown(results).items():
        lines.append(f"| {gate} | {failed} | {applied} |")
    lines += [
        "",
        "| failure mode | passed | gates failed |",
        "| ------------ | ------ | ------------ |",
    ]
    for mode, row in summary_by_mode(results).items():
        failed = ", ".join(f"{g} {n}" for g, n in row["failed_gates"].items()) or "none"
        lines.append(f"| {mode} | {row['passed']}/{row['total']} | {failed} |")
    lines += [
        "",
        "| case | tier | mode | pass | failed gates | cit_prec | cit_rec | ret_rec | faithful | notes |",
        "| ---- | ---- | ---- | ---- | ------------ | -------- | ------- | ------- | -------- | ----- |",
    ]
    order = {t: i for i, t in enumerate(DIFFICULTY_ORDER)}
    for r in sorted(results, key=lambda r: order.get(r.difficulty, len(order))):
        s = r.scores
        lines.append(
            f"| {r.case_id} | {r.difficulty} | {r.mode} | {'yes' if r.passed else 'no'} "
            f"| {', '.join(r.failed_gates) or 'none'} "
            f"| {s['citation_precision']:.2f} | {s['citation_recall']:.2f} "
            f"| {s['retrieval_recall']:.2f} | {s['faithfulness']:.2f} "
            f"| {'; '.join(r.notes)} |"
        )
    return "\n".join(lines) + "\n"
