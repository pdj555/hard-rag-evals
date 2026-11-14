"""Run Claude models through the suite, with a hard spending cap.

    python scripts/model_run.py --estimate                      # no calls: price the run
    python scripts/model_run.py --max-usd 10 --out OUT_DIR      # needs ANTHROPIC_API_KEY

A real run spends money and is started by hand, normally through the
`model-run` workflow. `--estimate` builds every request locally, estimates its
tokens from its length and prices it; it never builds a client.

Each model answers all 42 cases `--trials` times through the public view
(`hard_rag_evals/model_agent.py`). For every model and trial the run writes
`answers-MODEL-trialN.jsonl`, the exact file `hard-rag-evals grade` takes, the
report the grader makes of it, and `calls-MODEL-trialN.jsonl` with what each
case cost and how it ended. A case the model refused, answered with no usable
tool call, or could not be asked is written as an empty answer and counted as
failed. `summary.json` validates against
`hard_rag_evals/schemas/model_run.schema.json`.

The cap is checked before every request against the most that request can
cost. When it stops the run, the cases not asked are left out of the answers
files, the run is marked incomplete, and no claim is made from it.

With `--prereg`, the summary carries the preregistration's sha256 and every
setting where the run differs from it. A run that deviates, is incomplete, or
has too many request errors withholds its claims: the tests are still
printed, as exploratory. Exit codes: 0 the run finished and matches its
preregistration (or none was given), 1 it was incomplete or deviated, 2 usage.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from importlib import resources
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hard_rag_evals import cli, gamers, stats  # noqa: E402
from hard_rag_evals import model_agent as MA  # noqa: E402
from hard_rag_evals import report as R  # noqa: E402
from hard_rag_evals.failure_modes import ALL_CASES, DATASET_VERSION  # noqa: E402
from hard_rag_evals.provenance import CANARY, GRADER_VERSION  # noqa: E402
from hard_rag_evals.reference_agent import ReferenceAgent  # noqa: E402
from hard_rag_evals.runner import (  # noqa: E402
    DEFAULT_SHUFFLE_SEED,
    GATES,
    present,
    refusal_summary,
    run_suite,
)

SUMMARY_SCHEMA_VERSION = "1"
DEFAULT_MODELS = tuple(MA.PRICES)
DEFAULT_TRIALS = 3
ALPHA_WITHOUT_PREREG = 0.05

# Output tokens the estimate assumes for one request: adaptive thinking at the
# pinned effort plus a short answer. A guess meant to be high; no model has
# been run here, so nothing backs it. The ceiling printed beside the estimate
# assumes max_tokens on every attempt instead.
ESTIMATE_OUTPUT_TOKENS = 3000

# Files whose content decides what a model is sent and how it is scored.
CODE_FILES = (
    "hard_rag_evals/model_agent.py",
    "hard_rag_evals/prompts/model_agent_system.txt",
    "hard_rag_evals/runner.py",
    "hard_rag_evals/metrics.py",
    "hard_rag_evals/stats.py",
    "hard_rag_evals/report.py",
    "scripts/model_run.py",
)

PREREG_SETTINGS = (
    "models", "trials", "shuffle_seed", "effort", "max_tokens", "max_attempts",
    "prompt_sha256", "grader_version", "dataset_version", "best_surface_heuristic",
)


class UsageError(ValueError):
    pass


def load_schema() -> dict:
    path = resources.files("hard_rag_evals").joinpath("schemas/model_run.schema.json")
    return json.loads(path.read_text())


def code_sha256() -> str:
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode() + b"\0" + (ROOT / name).read_bytes() + b"\0")
    return digest.hexdigest()


def commit() -> str | None:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def presented(seed: int = DEFAULT_SHUFFLE_SEED) -> list[tuple[str, dict]]:
    """(descriptive id, public view) for every case, in public order, with
    documents shuffled by the seed. Only the public view goes to a model."""
    return [(c.id, R.public_case(present(c, seed))) for c in R.public_order(ALL_CASES)]


def budget_bound_ids() -> set[str]:
    """Cases whose corpus does not fit the retrieval budget. A model shown
    every document is not doing the retrieval task there; see README."""
    out = set()
    for c in ALL_CASES:
        chars = sum(len(d.text) for d in c.corpus.documents)
        if len(c.corpus.documents) > c.budget.max_docs or chars > c.budget.max_chars:
            out.add(c.id)
    return out


# ---------------------------------------------------------------- estimate

def estimate(models: list[str], trials: int, seed: int = DEFAULT_SHUFFLE_SEED) -> dict:
    """What the run is expected to cost, from request lengths. No calls."""
    cases = presented(seed)
    rows = []
    for model in models:
        requests = [MA.build_request(model, public) for _, public in cases]
        tokens_in = sum(MA.estimate_input_tokens(r) for r in requests) * trials
        calls = len(requests) * trials
        usage = {"input_tokens": tokens_in, "output_tokens": calls * ESTIMATE_OUTPUT_TOKENS}
        ceiling = sum(MA.worst_case_cost(r, model) for r in requests) * trials
        rows.append({
            "model": model,
            "calls": calls,
            **usage,
            "usd": round(MA.cost(usage, model), 4),
            "ceiling_usd": round(ceiling * MA.SETTINGS["max_attempts"], 4),
        })
    largest = max(MA.estimate_input_tokens(MA.build_request(models[0], p)) for _, p in cases)
    return {
        "kind": "model_run_estimate",
        "assumptions": {
            "chars_per_token": MA.CHARS_PER_TOKEN,
            "request_overhead_tokens": MA.REQUEST_OVERHEAD_TOKENS,
            "output_tokens_per_call": ESTIMATE_OUTPUT_TOKENS,
            "attempts_per_case": 1,
            "ceiling": "max_tokens of output on every attempt, max_attempts attempts per case",
        },
        "cases": len(cases),
        "trials": trials,
        "shuffle_seed": seed,
        "largest_request_input_tokens": largest,
        "prices_per_million": {m: list(MA.PRICES[m]) for m in models},
        "rows": rows,
        "total_usd": round(sum(r["usd"] for r in rows), 2),
        "total_ceiling_usd": round(sum(r["ceiling_usd"] for r in rows), 2),
    }


def render_estimate(est: dict, max_usd: float | None) -> str:
    a = est["assumptions"]
    lines = [
        f"{est['cases']} cases x {est['trials']} trials, seed {est['shuffle_seed']}. "
        f"Assumes {a['chars_per_token']} characters per token plus "
        f"{a['request_overhead_tokens']} tokens per request, "
        f"{a['output_tokens_per_call']} output tokens per call, one attempt per case.",
    ]
    for r in est["rows"]:
        lines.append(
            f"{r['model']}: {r['calls']} calls, {r['input_tokens']} input and "
            f"{r['output_tokens']} output tokens, ${r['usd']:.2f} "
            f"(ceiling ${r['ceiling_usd']:.2f})"
        )
    lines.append(
        f"estimated total: ${est['total_usd']:.2f}; ceiling ${est['total_ceiling_usd']:.2f} "
        f"({a['ceiling']})"
    )
    if max_usd is not None:
        lines.append(
            f"--max-usd {max_usd:.2f}: the run stops before the request that could pass it"
            + ("" if est["total_usd"] <= max_usd else "; THE ESTIMATE IS ABOVE THE CAP")
        )
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ prereg

def load_prereg(path: Path) -> dict:
    """A preregistration with the sha256 of its bytes. Refuses one that does
    not state every setting the audit compares."""
    try:
        raw = Path(path).read_bytes()
        doc = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot read the preregistration {path}: {exc}") from None
    if not isinstance(doc, dict) or not isinstance(doc.get("settings"), dict):
        raise UsageError("the preregistration needs a 'settings' object")
    missing = [k for k in PREREG_SETTINGS if k not in doc["settings"]]
    if missing:
        raise UsageError(f"the preregistered settings need: {', '.join(missing)}")
    thresholds = doc.get("thresholds")
    if not isinstance(thresholds, dict) or set(thresholds) != {"alpha", "max_share_errors"}:
        raise UsageError("the preregistered thresholds are exactly: alpha, max_share_errors")
    for key, top in (("alpha", 0.2), ("max_share_errors", 1.0)):
        value = thresholds[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= top:
            raise UsageError(f"the preregistered {key} must be a number above 0 and at most {top}")
    for key in ("name", "written"):
        if not isinstance(doc.get(key), str) or not doc[key].strip():
            raise UsageError(f"the preregistration needs {key!r}")
    try:
        shown = str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        shown = str(path)
    return {**doc, "sha256": hashlib.sha256(raw).hexdigest(), "path": shown}


def run_settings(models: list[str], trials: int, seed: int, best_surface: str) -> dict:
    return {
        "models": list(models),
        "trials": trials,
        "shuffle_seed": seed,
        "effort": MA.SETTINGS["effort"],
        "max_tokens": MA.SETTINGS["max_tokens"],
        "max_attempts": MA.SETTINGS["max_attempts"],
        "prompt_sha256": MA.prompt_sha256(),
        "grader_version": GRADER_VERSION,
        "dataset_version": DATASET_VERSION,
        "best_surface_heuristic": best_surface,
    }


def deviations(prereg: dict, actual: dict) -> list[dict]:
    out = []
    for key in PREREG_SETTINGS:
        want, got = prereg["settings"][key], actual[key]
        same = sorted(want) == sorted(got) if key == "models" else want == got
        if not same:
            out.append({"setting": key, "preregistered": want, "run": got})
    return out


# --------------------------------------------------------------- baselines

def baselines(seed: int) -> dict:
    """The reference agent and the best copy-one-document agent at the seed,
    as {case id: passed}. Best is the highest pass count, ties to the name
    that sorts first. Both are scripted; no model is involved."""
    reference = {r.case_id: r.passed for r in run_suite(ReferenceAgent(), shuffle_seed=seed)}
    surface = {}
    for cls in gamers.SURFACE:
        agent = cls()
        surface[agent.name] = {r.case_id: r.passed for r in run_suite(agent, shuffle_seed=seed)}
    best = min(surface, key=lambda name: (-sum(surface[name].values()), name))
    return {"reference": reference, "best_surface": surface[best], "best_surface_name": best}


def _rate(k: int, n: int) -> dict:
    lo, hi = stats.clopper_pearson(k, n)
    return {"passed": k, "total": n, "rate": k / n, "ci95": [lo, hi]}


def _paired(name: str, against: str, base: dict[str, bool], other: dict[str, bool]) -> dict:
    """`other` against `base` on the same cases: exact McNemar."""
    if set(base) != set(other):
        raise ValueError("a paired comparison needs the same cases on both sides")
    gained = sum(other[c] and not base[c] for c in base)
    lost = sum(base[c] and not other[c] for c in base)
    n = len(base)
    lo, hi = stats.paired_difference_ci(gained, lost, n)
    return {
        "model": name, "against": against, "n": n, "gained": gained, "lost": lost,
        "difference": (gained - lost) / n, "ci95": [lo, hi],
        "p_value": stats.mcnemar_exact(gained, lost), "p_holm": None,
    }


def _holm(rows: list[dict]) -> list[dict]:
    for row, p in zip(rows, stats.holm([r["p_value"] for r in rows])):
        row["p_holm"] = p
    return rows


# --------------------------------------------------------------------- run

def _slug(model: str, trial: int) -> str:
    return f"{model}-trial{trial}"


def write_answers(path: Path, outcomes: list[MA.Outcome]) -> None:
    """The answers file for `hard-rag-evals grade`: one line per case that
    was asked. A case with no answer from the model gets the failure answer;
    a case the cap stopped before is left out."""
    lines = []
    for o in outcomes:
        if o.status == MA.NOT_RUN:
            continue
        a = o.answer if o.status == MA.ANSWERED else MA.failure_answer()
        lines.append(json.dumps({
            "case_id": o.public_id, "text": a.text, "citations": a.citations,
            "abstained": a.abstained, "retrieved_ids": a.retrieved_ids,
        }, ensure_ascii=False))
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")


def write_calls(path: Path, outcomes: list[MA.Outcome]) -> None:
    rows = [{
        "case_id": o.public_id, "status": o.status, "attempts": o.attempts,
        "usage": o.usage, "usd": o.usd, "stop_reasons": o.stop_reasons, "detail": o.detail,
        "estimated_input_tokens": o.estimated_input_tokens,
    } for o in outcomes]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def grade_file(path: Path, agent_name: str, seed: int):
    """Grade an answers file the way `hard-rag-evals grade --allow-partial`
    does, from the bytes on disk. Returns the results and the report."""
    text = R.decode_utf8(path.read_bytes(), path.name)
    answers = R.parse_answers_jsonl(text, path.name)
    results, missing = cli.grade_answers(answers, allow_partial=True, allow_descriptive=False)
    for r in results:
        r.shuffle_seed = seed
    config = {
        "source": "answers_file", "difficulty": None, "modes": None, "shuffle_seed": seed,
        "missing_case_ids": missing, "total_cases": len(ALL_CASES),
    }
    document = R.report_document(agent_name, results, config) if results else None
    return results, document


def run_model(model: str, trials: int, client, budget: MA.Budget, seed: int, out: Path) -> list:
    """Every trial of one model. Returns, per trial, (outcomes, results).
    Once the cap has stopped a request nothing more is asked."""
    agent = MA.ModelAgent(model, client, budget)
    cases = presented(seed)
    done = []
    for trial in range(1, trials + 1):
        outcomes = []
        for _, public in cases:
            if budget.stopped:
                outcomes.append(MA.Outcome(public["id"], MA.NOT_RUN, detail="cap reached"))
            else:
                outcomes.append(agent.answer_case(public))
        slug = _slug(model, trial)
        write_answers(out / f"answers-{slug}.jsonl", outcomes)
        write_calls(out / f"calls-{slug}.jsonl", outcomes)
        results, document = grade_file(out / f"answers-{slug}.jsonl", slug, seed)
        if document is not None:
            (out / f"report-{slug}.json").write_text(json.dumps(document) + "\n", encoding="utf-8")
        done.append((outcomes, results))
    return done


def model_summary(trial_data: list, bound: set[str]) -> dict:
    """One model's numbers from its trials. A case passes a trial only when
    the model answered it and the grader passed the answer."""
    n_cases = len(ALL_CASES)
    by_public = {R.public_id(c.id): c for c in ALL_CASES}
    statuses = dict.fromkeys(MA.STATUSES, 0)
    tokens = dict.fromkeys(MA.USAGE_KEYS, 0)
    usd, estimated_in, attempts = 0.0, 0, 0
    per_trial, verdicts = [], []
    gates = {g: {"failed": 0, "applicable": 0} for g in GATES}
    by_mode: dict[str, dict] = {}
    abstained = answerable = 0
    for number, (outcomes, results) in enumerate(trial_data, start=1):
        graded = {r.case_id: r for r in results}
        status = {by_public[o.public_id].id: o.status for o in outcomes}
        verdict = {
            cid: graded[cid].passed and status[cid] == MA.ANSWERED
            for cid in graded
        }
        trial_statuses = dict.fromkeys(MA.STATUSES, 0)
        for o in outcomes:
            trial_statuses[o.status] += 1
            statuses[o.status] += 1
            attempts += o.attempts
            usd += o.usd
            if o.attempts:
                estimated_in += o.estimated_input_tokens * o.attempts
            for key, value in o.usage.items():
                tokens[key] += value
        complete = len(graded) == n_cases
        row = {"trial": number, "complete": complete, "graded": len(graded),
               "statuses": trial_statuses, "passed": None, "over_refusal": None,
               "correct_abstention": None}
        if complete:
            row["passed"] = _rate(sum(verdict.values()), n_cases)
            row.update(refusal_summary(results))
            verdicts.append(verdict)
            for r in results:
                for gate, ok in r.gates.items():
                    gates[gate]["applicable"] += 1
                    gates[gate]["failed"] += not ok
                mode = by_mode.setdefault(r.mode, {"passed": 0, "total": 0, "failed_gates": {}})
                mode["passed"] += verdict[r.case_id]
                mode["total"] += 1
                for gate in r.failed_gates:
                    mode["failed_gates"][gate] = mode["failed_gates"].get(gate, 0) + 1
                if not r.should_abstain:
                    answerable += 1
                    abstained += r.abstained
        per_trial.append(row)
    complete = bool(verdicts) and len(verdicts) == len(trial_data)
    out = {
        "complete": complete,
        "trials_completed": len(verdicts),
        "attempts": attempts,
        "statuses": statuses,
        "tokens": tokens,
        "estimated_input_tokens": estimated_in,
        "usd": usd,
        "per_trial": per_trial,
        "all_trials": None, "any_trial": None, "spread": None,
        "budget_bound": None, "not_budget_bound": None,
        "gates": None, "by_mode": None, "over_refusal": None,
    }
    if not complete:
        return out
    ids = [c.id for c in ALL_CASES]
    strict = {cid: all(v[cid] for v in verdicts) for cid in ids}
    loose = {cid: any(v[cid] for v in verdicts) for cid in ids}
    counts = [sum(v.values()) for v in verdicts]
    out["all_trials"] = _rate(sum(strict.values()), n_cases)
    out["any_trial"] = _rate(sum(loose.values()), n_cases)
    out["spread"] = {
        "passed_by_trial": counts, "min": min(counts), "max": max(counts),
        "mean": sum(counts) / len(counts), "range": max(counts) - min(counts),
        "unstable_cases": sum(strict[c] != loose[c] for c in ids),
    }
    inside = [c for c in ids if c in bound]
    outside = [c for c in ids if c not in bound]
    out["budget_bound"] = _rate(sum(strict[c] for c in inside), len(inside))
    out["not_budget_bound"] = _rate(sum(strict[c] for c in outside), len(outside))
    out["gates"] = {g: row for g, row in gates.items() if row["applicable"]}
    out["by_mode"] = by_mode
    out["over_refusal"] = {
        "abstained": abstained, "total": answerable, "rate": abstained / answerable,
        "note": "pooled over trials, which repeat the same cases; no interval",
    }
    out["_strict"] = strict
    return out


def summarize(record: dict, per_model: dict[str, dict], prereg: dict | None) -> dict:
    """The summary document. `per_model` comes from model_summary."""
    seed = record["shuffle_seed"]
    base = baselines(seed)
    strict = {m: s.pop("_strict") for m, s in per_model.items() if "_strict" in s}
    for s in per_model.values():
        s.pop("_strict", None)

    primary = []
    for model, verdict in strict.items():
        primary.append(_paired(model, "reference", base["reference"], verdict))
        primary.append(_paired(model, base["best_surface_name"], base["best_surface"], verdict))
    between = [_paired(b, a, strict[a], strict[b]) for a, b in combinations(strict, 2)]
    _holm(primary)
    _holm(between)

    complete = (
        record["fatal_error"] is None
        and not record["stopped_by_cap"]
        and set(per_model) == set(record["models"])
        and all(s["complete"] for s in per_model.values())
    )
    actual = run_settings(record["models"], record["trials"], seed, base["best_surface_name"])
    audit = None
    alpha = ALPHA_WITHOUT_PREREG
    reason = None
    if prereg is None:
        reason = "no preregistration was given, so every test is exploratory"
    else:
        alpha = prereg["thresholds"]["alpha"]
        found = deviations(prereg, actual)
        audit = {"name": prereg["name"], "written": prereg["written"], "path": prereg["path"],
                 "sha256": prereg["sha256"], "deviations": found}
        limit = prereg["thresholds"]["max_share_errors"]
        noisy = [
            m for m, s in per_model.items()
            if s["statuses"][MA.ERROR] > limit * sum(s["statuses"].values())
        ]
        if found:
            reason = "settings deviate from the preregistration: " + ", ".join(
                d["setting"] for d in found)
        elif not complete:
            reason = "the run is incomplete"
        elif noisy:
            reason = (f"more than {limit:.0%} of cases ended in a request error for: "
                      + ", ".join(noisy))
    if reason is None and not complete:
        reason = "the run is incomplete"
    allowed = reason is None
    significant = [
        {"model": r["model"], "against": r["against"], "family": family}
        for family, rows in (("primary", primary), ("between_models", between))
        for r in rows if allowed and r["p_holm"] < alpha
    ]
    return {
        "kind": "model_run",
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "grader_version": GRADER_VERSION,
        "dataset_version": DATASET_VERSION,
        "canary": CANARY,
        "shuffle_seed": seed,
        "prompt_sha256": MA.prompt_sha256(),
        "code_sha256": code_sha256(),
        "commit": commit(),
        "models": record["models"],
        "trials": record["trials"],
        "settings": MA.SETTINGS,
        "prices_per_million": {m: list(MA.PRICES[m]) for m in record["models"]},
        "max_usd": record["max_usd"],
        "spent_usd": record["spent_usd"],
        "unmeasured_usd": record["unmeasured_usd"],
        "complete": complete,
        "stopped_by_cap": record["stopped_by_cap"],
        "fatal_error": record["fatal_error"],
        "prereg": audit,
        "claims": {"allowed": allowed, "reason": reason, "alpha": alpha,
                   "significant": significant},
        "baselines": {
            "reference": _rate(sum(base["reference"].values()), len(ALL_CASES)),
            "best_surface": {"agent": base["best_surface_name"],
                             **_rate(sum(base["best_surface"].values()), len(ALL_CASES))},
        },
        "budget_bound_cases": len(budget_bound_ids()),
        "per_model": per_model,
        "comparisons": {"primary": primary, "between_models": between},
    }


def render_summary(summary: dict) -> str:
    c = summary["claims"]
    lines = [
        "# Model run",
        "",
        f"Grader {summary['grader_version']}, dataset {summary['dataset_version'][:12]}, "
        f"seed {summary['shuffle_seed']}, prompt sha256 {summary['prompt_sha256'][:12]}, "
        f"{summary['trials']} trials. Spent ${summary['spent_usd']:.2f} of a "
        f"${summary['max_usd']:.2f} cap.",
        "",
        "Preregistration: " + (
            f"{summary['prereg']['path']}, sha256 {summary['prereg']['sha256']}."
            if summary["prereg"] else "none given."),
        "",
        ("Claims allowed." if c["allowed"] else f"**No claim is made: {c['reason']}.** "
         "Every test below is exploratory."),
        "",
        "A case counts as passed only if it passed in every trial.",
        "",
        "| model | every trial | 95% interval | any trial | by trial | refused | invalid | errors | usd |",
        "| ----- | ----------- | ------------ | --------- | -------- | ------- | ------- | ------ | --- |",
    ]
    for model, s in summary["per_model"].items():
        st = s["statuses"]
        if s["complete"]:
            a, lo, hi = s["all_trials"], *s["all_trials"]["ci95"]
            cells = (f"{a['passed']}/{a['total']} | {lo:.2f} to {hi:.2f} | "
                     f"{s['any_trial']['passed']}/{a['total']} | "
                     f"{', '.join(map(str, s['spread']['passed_by_trial']))}")
        else:
            cells = f"incomplete ({s['trials_completed']} trials) | | | "
        lines.append(f"| {model} | {cells} | {st['refused']} | {st['invalid']} "
                     f"| {st['error']} | {s['usd']:.2f} |")
    b = summary["baselines"]
    lines += [
        "",
        f"Scripted baselines at the same seed: reference {b['reference']['passed']}/42, "
        f"{b['best_surface']['agent']} {b['best_surface']['passed']}/42.",
        "",
        "| comparison | gained | lost | p | Holm p |",
        "| ---------- | ------ | ---- | - | ------ |",
    ]
    for family in ("primary", "between_models"):
        for r in summary["comparisons"][family]:
            lines.append(f"| {r['model']} vs {r['against']} ({family}) | {r['gained']} "
                         f"| {r['lost']} | {r['p_value']:.3f} | {r['p_holm']:.3f} |")
    lines += ["", CANARY]
    return "\n".join(lines) + "\n"


def run(models: list[str], trials: int, max_usd: float, out: Path, client,
        prereg: dict | None = None, seed: int = DEFAULT_SHUFFLE_SEED) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    budget = MA.Budget(max_usd)
    bound = budget_bound_ids()
    per_model: dict[str, dict] = {}
    fatal = None
    for model in models:
        if budget.stopped:
            break
        try:
            per_model[model] = model_summary(run_model(model, trials, client, budget, seed, out), bound)
        except MA.FatalModelError as exc:
            fatal = str(exc)
            break
    record = {
        "models": list(models), "trials": trials, "shuffle_seed": seed, "max_usd": max_usd,
        "spent_usd": budget.spent, "unmeasured_usd": budget.unmeasured,
        "stopped_by_cap": budget.stopped, "fatal_error": fatal,
    }
    summary = summarize(record, per_model, prereg)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out / "summary.md").write_text(render_summary(summary), encoding="utf-8")
    return summary


def build_client():
    try:
        import anthropic
    except ImportError as exc:
        raise UsageError(
            f"a real run needs the models extra: pip install -e '.[models]' ({exc})"
        ) from None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise UsageError("ANTHROPIC_API_KEY is not set; a real run needs it")
    return anthropic.Anthropic(
        max_retries=MA.SETTINGS["sdk_max_retries"], timeout=MA.SETTINGS["sdk_timeout_seconds"]
    )


def main(argv: list[str] | None = None, client_factory=build_client) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS),
                        help="model ids, comma separated")
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--max-usd", type=float, default=None,
                        help="hard cap on spend for the whole run; required for a real run")
    parser.add_argument("--estimate", action="store_true",
                        help="price the run from request lengths; no calls, no client")
    parser.add_argument("--out", type=Path, default=None, help="directory for the run's files")
    parser.add_argument("--prereg", type=Path, default=None,
                        help="a preregistration (docs/prereg/*.json) to check the run against")
    args = parser.parse_args(argv)
    try:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
        unknown = [m for m in models if m not in MA.PRICES]
        if unknown or not models or len(set(models)) != len(models):
            raise UsageError(f"--models must be distinct ids from {sorted(MA.PRICES)}")
        if args.trials < 1:
            raise UsageError("--trials must be 1 or more")
        if args.max_usd is not None and not args.max_usd > 0:
            raise UsageError("--max-usd must be above 0")
        prereg = load_prereg(args.prereg) if args.prereg else None
        if prereg:
            print(f"preregistration {prereg['path']} sha256 {prereg['sha256']}")
        if args.estimate:
            est = estimate(models, args.trials)
            print(render_estimate(est, args.max_usd), end="")
            if args.out:
                args.out.mkdir(parents=True, exist_ok=True)
                (args.out / "estimate.json").write_text(json.dumps(est, indent=2) + "\n")
            return 0
        if args.max_usd is None or args.out is None:
            raise UsageError("a real run needs --max-usd and --out")
        client = client_factory()
    except UsageError as exc:
        print(f"model_run: error: {exc}", file=sys.stderr)
        return 2
    summary = run(models, args.trials, args.max_usd, args.out, client, prereg)
    print(render_summary(summary), end="")
    if summary["fatal_error"]:
        print(f"model_run: stopped: {summary['fatal_error']}", file=sys.stderr)
    ok = summary["complete"] and not (summary["prereg"] and summary["prereg"]["deviations"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
