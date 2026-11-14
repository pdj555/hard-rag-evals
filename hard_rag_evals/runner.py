"""Eval runner: executes every case against an agent and grades the answers.

Grading is strict and fully deterministic. A case passes only when every
applicable check holds: required citations present, forbidden citations
absent, every citation names a real document, abstention matches the
expected behavior, and contradictions are stated claim against claim.
"""
from __future__ import annotations

import random
from dataclasses import replace

from . import metrics as M
from . import stats
from .failure_modes import ALL_CASES
from .provenance import DATASET_VERSION, GRADER_VERSION
from .types import Agent, Corpus, EvalCase, EvalResult

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
        abstained=bool(answer.abstained),
        should_abstain=case.should_abstain,
        grader_version=GRADER_VERSION,
        dataset_version=DATASET_VERSION,
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


def permute_documents(case: EvalCase, seed: int) -> EvalCase:
    """The same case with its documents in a different order.

    Document order carries no meaning in any case, so neither the grader's
    verdict nor a sound agent's answer should depend on it. The permutation
    is fixed by the seed and the case id, so a run can be repeated exactly.
    """
    docs = list(case.corpus.documents)
    random.Random(f"{seed}:{case.id}").shuffle(docs)
    return replace(case, corpus=Corpus(documents=tuple(docs)))


def run_suite(
    agent: Agent,
    difficulty: str | tuple[str, ...] | None = None,
    modes: str | tuple[str, ...] | None = None,
    shuffle_seed: int | None = None,
) -> list[EvalResult]:
    """Grade the agent on every case, or on the tiers and modes asked for.

    With shuffle_seed set, each case's documents are permuted with that seed
    before the agent sees them. None keeps the order written in the fixture.
    """
    results = []
    for case in select_cases(difficulty, modes):
        if shuffle_seed is not None:
            case = permute_documents(case, shuffle_seed)
        results.append(grade(case, agent.answer(case.query, case.corpus, case.budget)))
    return results


def order_spread(agent: Agent, seeds: tuple[int, ...] = tuple(range(20))) -> dict:
    """How much the agent's result moves when only document order changes.

    Returns the pass count in fixture order, the pass count under each seed,
    their min and max, and the cases whose verdict changed under any seed.
    An empty flipped list means the agent is order invariant on these seeds,
    not that it is in general.
    """
    base = {r.case_id: r.passed for r in run_suite(agent)}
    counts: dict[int, int] = {}
    flipped: set[str] = set()
    for seed in seeds:
        results = run_suite(agent, shuffle_seed=seed)
        counts[seed] = sum(r.passed for r in results)
        flipped |= {r.case_id for r in results if r.passed != base[r.case_id]}
    return {
        "fixture_order": sum(base.values()),
        "by_seed": counts,
        "min": min(counts.values()),
        "max": max(counts.values()),
        "flipped": sorted(flipped),
    }


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


def refusal_summary(results: list[EvalResult]) -> dict[str, dict | None]:
    """The two ways abstention goes wrong, counted on separate denominators.

    over_refusal: of the answerable cases, how many the agent refused.
    correct_abstention: of the unanswerable cases, how many it refused.
    Each holds abstained, total, rate and an exact 95% interval, or is None
    when the results hold no case of that kind. An agent that refuses
    everything scores 1.0 on both; one that never refuses scores 0.0 on both.
    """

    def rate(rows: list[EvalResult]) -> dict | None:
        if not rows:
            return None
        k = sum(r.abstained for r in rows)
        lo, hi = stats.clopper_pearson(k, len(rows))
        return {"abstained": k, "total": len(rows), "rate": k / len(rows), "ci95": [lo, hi]}

    return {
        "over_refusal": rate([r for r in results if not r.should_abstain]),
        "correct_abstention": rate([r for r in results if r.should_abstain]),
    }


def render_markdown(agent_name: str, results: list[EvalResult]) -> str:
    passed = sum(1 for r in results if r.passed)
    lines = [
        f"# Eval report: {agent_name}",
        "",
        f"**{passed}/{len(results)} cases passed.** Grader version {GRADER_VERSION}, "
        f"dataset version {DATASET_VERSION[:12]}.",
        "",
    ]
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
    lines += ["", "| abstention | abstained | rate | 95% interval |", "| --- | --- | --- | --- |"]
    labels = {
        "over_refusal": "over-refusal (answerable cases refused)",
        "correct_abstention": "correct abstention (unanswerable cases refused)",
    }
    for key, row in refusal_summary(results).items():
        if row is not None:
            lo, hi = row["ci95"]
            lines.append(
                f"| {labels[key]} | {row['abstained']}/{row['total']} | {row['rate']:.2f} "
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
