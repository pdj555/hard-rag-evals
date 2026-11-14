"""The model runner, driven by a fake client. No network, no key, no spend."""
import hashlib
import importlib.util
import inspect
import json
import re
from pathlib import Path

import jsonschema
import pytest

from hard_rag_evals import cli, stats
from hard_rag_evals import model_agent as MA
from hard_rag_evals import report as R
from hard_rag_evals.failure_modes import ALL_CASES
from hard_rag_evals.runner import DEFAULT_SHUFFLE_SEED, grade, present

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("model_run", ROOT / "scripts" / "model_run.py")
MR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MR)

PREREG = ROOT / "docs" / "prereg" / "model-run-1.json"
VALIDATOR = jsonschema.Draft202012Validator(MR.load_schema())
GOLD = json.loads((ROOT / "tests" / "gold_answers.json").read_text())
GOLD.pop("_canary")
BY_PUBLIC = {R.public_id(c.id): c for c in ALL_CASES}
HAIKU, SONNET, OPUS = "claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"
USAGE = {"input_tokens": 500, "output_tokens": 200}


def tool_response(payload: dict, usage: dict = USAGE) -> dict:
    return {
        "stop_reason": "tool_use",
        "content": [
            {"type": "thinking", "thinking": ""},
            {"type": "tool_use", "id": "toolu_1", "name": MA.TOOL_NAME, "input": payload},
        ],
        "usage": usage,
    }


def gold_payload(case_id: str) -> dict:
    g = GOLD[case_id]
    return {"text": g["text"], "citations": list(g["citations"]), "abstained": g["abstained"],
            "retrieved_ids": list(g["retrieved_ids"])}


class ApiError(Exception):
    def __init__(self, status_code=None):
        super().__init__("boom")
        if status_code is not None:
            self.status_code = status_code


class FakeClient:
    """Answers every case with its gold answer unless `behave` says otherwise.

    behave(case_id, model, nth) gets the descriptive case id, the model, and
    how many times this model has been asked this case before (0 first). It
    returns None for the gold answer, a dict to use as the response, or an
    exception to raise.
    """

    def __init__(self, behave=None, usage=USAGE):
        self.messages = self
        self.requests: list[dict] = []
        self.seen: dict = {}
        self.behave = behave or (lambda case_id, model, nth: None)
        self.usage = usage

    def create(self, **kwargs):
        self.requests.append(kwargs)
        public_id = re.match(r"Case (c-[0-9a-f]{12}) ", kwargs["messages"][0]["content"]).group(1)
        case_id = BY_PUBLIC[public_id].id
        key = (kwargs["model"], case_id)
        nth = self.seen.get(key, 0)
        self.seen[key] = nth + 1
        result = self.behave(case_id, kwargs["model"], nth)
        if isinstance(result, Exception):
            raise result
        return result if result is not None else tool_response(gold_payload(case_id), self.usage)


def valid(summary: dict) -> dict:
    VALIDATOR.validate(summary)
    return summary


# ------------------------------------------------------- what the model sees

def test_the_request_is_built_from_the_public_view_and_nothing_else():
    for case in ALL_CASES:
        public = R.public_case(present(case, DEFAULT_SHUFFLE_SEED))
        request = MA.build_request(OPUS, public)
        assert [m["role"] for m in request["messages"]] == ["user"]
        user = request["messages"][0]["content"]
        assert user == MA.render_case(public)
        sent = json.dumps(request)
        # The descriptive id names the failure mode ("unanswerable-easy").
        assert case.id not in sent, case.id
        own_text = case.query + " ".join(d.id + d.text + d.source for d in case.corpus.documents)
        if case.mode not in own_text:
            assert case.mode not in sent, case.mode
        assert public["id"] in user and case.query in user
        # Documents appear in the shuffled order, not fixture order.
        positions = [user.index(f"<document id={json.dumps(d['id'])} ") for d in public["documents"]]
        assert positions == sorted(positions)


def test_render_case_reads_only_public_keys():
    """A key the public view does not have cannot reach the prompt: a dev-view
    case renders the same text as the public one."""
    case = ALL_CASES[0]
    shown = present(case, DEFAULT_SHUFFLE_SEED)
    assert MA.render_case(R.public_case(shown, dev=True)) == MA.render_case(R.public_case(shown))


def test_presented_cases_are_shuffled_at_the_published_seed_in_public_order():
    cases = MR.presented()
    assert [p["id"] for _, p in cases] == sorted(R.public_id(c.id) for c in ALL_CASES)
    for case_id, public in cases:
        case = next(c for c in ALL_CASES if c.id == case_id)
        assert [d["id"] for d in public["documents"]] == [
            d.id for d in present(case, 2026).corpus.documents
        ]
        assert "mode" not in public and "case_id" not in public


def test_request_arguments_are_ones_the_sdk_accepts():
    anthropic = pytest.importorskip("anthropic")
    request = MA.build_request(HAIKU, MR.presented()[0][1])
    accepted = set(inspect.signature(anthropic.resources.messages.Messages.create).parameters)
    assert set(request) <= accepted
    assert "temperature" not in request
    assert request["tool_choice"] == {"type": "auto", "disable_parallel_tool_use": True}
    assert request["output_config"] == {"effort": "medium"}
    assert request["tools"][0]["strict"] is True
    assert request["tools"][0]["input_schema"]["additionalProperties"] is False


def test_prompt_hash_covers_the_system_prompt_and_the_tool(monkeypatch):
    before = MA.prompt_sha256()
    monkeypatch.setitem(MA.ANSWER_TOOL, "description", "changed")
    assert MA.prompt_sha256() != before


# ------------------------------------------------------------- answers file

def test_answers_file_is_accepted_by_grade_and_gold_answers_pass(tmp_path, capsys):
    summary = valid(MR.run([HAIKU], 1, 5.0, tmp_path, FakeClient()))
    path = tmp_path / f"answers-{HAIKU}-trial1.jsonl"
    code = cli.main(["grade", str(path), "--json"])
    report = json.loads(capsys.readouterr().out)
    assert code == 0 and report["summary"]["passed"] == 42
    assert summary["per_model"][HAIKU]["all_trials"]["passed"] == 42
    # The report the run wrote is the grader's own document.
    written = json.loads((tmp_path / f"report-{HAIKU}-trial1.json").read_text())
    jsonschema.Draft202012Validator(R.load_schema()).validate(written)
    assert written["summary"]["passed"] == 42 and written["config"]["shuffle_seed"] == 2026


def test_the_failure_answer_fails_every_case():
    assert not any(grade(c, MA.failure_answer()).passed for c in ALL_CASES)


# ---------------------------------------------------- refusals, errors, retry

def test_refusals_errors_and_unusable_calls_are_failures_and_are_not_dropped(tmp_path, capsys):
    ids = [c.id for c in ALL_CASES]
    refused, errored, invalid, recovered = ids[0], ids[1], ids[2], ids[3]

    def behave(case_id, model, nth):
        if case_id == refused:
            return {"stop_reason": "refusal", "stop_details": {"category": "cyber"},
                    "content": [], "usage": USAGE}
        if case_id == errored:
            return ApiError()
        if case_id == invalid:
            return {"stop_reason": "end_turn", "content": [{"type": "text", "text": "42"}],
                    "usage": USAGE}
        if case_id == recovered and nth == 0:
            return tool_response({"text": "x", "citations": "not-a-list", "abstained": False,
                                  "retrieved_ids": []})
        return None

    client = FakeClient(behave)
    summary = valid(MR.run([HAIKU], 1, 5.0, tmp_path, client))
    row = summary["per_model"][HAIKU]
    assert row["statuses"] == {"answered": 39, "refused": 1, "invalid": 1, "error": 1, "not_run": 0}
    assert row["all_trials"]["passed"] == 39 and row["complete"]
    # A refusal is not retried; an error and an unusable call are, once.
    assert client.seen[(HAIKU, refused)] == 1
    assert client.seen[(HAIKU, errored)] == client.seen[(HAIKU, invalid)] == 2
    assert client.seen[(HAIKU, recovered)] == 2
    assert row["attempts"] == 42 + 3
    # Every case is in the answers file, and grade fails exactly the three.
    path = tmp_path / f"answers-{HAIKU}-trial1.jsonl"
    assert len(path.read_text().splitlines()) == 42
    code = cli.main(["grade", str(path), "--json"])
    report = json.loads(capsys.readouterr().out)
    assert code == 1
    assert {r["case_id"] for r in report["results"] if not r["passed"]} == {refused, errored, invalid}
    calls = [json.loads(line) for line in (tmp_path / f"calls-{HAIKU}-trial1.jsonl").read_text().splitlines()]
    by_id = {BY_PUBLIC[c["case_id"]].id: c for c in calls}
    assert by_id[refused]["detail"] == "refusal (cyber)"
    assert by_id[errored]["status"] == "error" and by_id[errored]["usage"] == {}
    # Billed attempts are all counted, including the one that was retried.
    assert by_id[recovered]["usage"]["input_tokens"] == 2 * USAGE["input_tokens"]


def test_a_passing_answer_does_not_rescue_a_case_the_model_did_not_answer(tmp_path):
    """Status decides before the grader does: if the failure answer ever
    passed a case, a refusal on it would still count as failed."""
    outcome = MA.Outcome(R.public_id(ALL_CASES[0].id), MA.REFUSED)
    result = grade(ALL_CASES[0], MA.Answer(**gold_payload(ALL_CASES[0].id)))
    assert result.passed
    outcomes = [outcome] + [
        MA.Outcome(R.public_id(c.id), MA.ANSWERED, answer=MA.Answer(**gold_payload(c.id)))
        for c in ALL_CASES[1:]
    ]
    results = [result] + [grade(c, MA.Answer(**gold_payload(c.id))) for c in ALL_CASES[1:]]
    row = MR.model_summary([(outcomes, results)], MR.budget_bound_ids())
    assert row["all_trials"]["passed"] == 41


def test_a_request_the_api_rejects_stops_the_run_instead_of_failing_42_cases(tmp_path):
    client = FakeClient(lambda case_id, model, nth: ApiError(401))
    summary = valid(MR.run([HAIKU, SONNET], 1, 5.0, tmp_path, client))
    assert len(client.requests) == 1
    assert "HTTP 401" in summary["fatal_error"]
    assert not summary["complete"] and not summary["claims"]["allowed"]
    assert summary["per_model"] == {} and summary["comparisons"]["primary"] == []


# ------------------------------------------------------------------- the cap

def test_the_cap_stops_before_the_request_that_could_pass_it(tmp_path):
    usage = {"input_tokens": 2000, "output_tokens": 8000}  # $0.0048 a call on haiku
    client = FakeClient(usage=usage)
    cap = 0.05
    summary = valid(MR.run([HAIKU, SONNET], 3, cap, tmp_path, client))
    per_call = MA.cost(usage, HAIKU)
    assert summary["spent_usd"] <= cap
    assert summary["spent_usd"] == pytest.approx(per_call * len(client.requests))
    # It stopped early, with room for less than one worst-case request left.
    assert 0 < len(client.requests) < 42
    last = MA.build_request(HAIKU, MR.presented()[len(client.requests)][1])
    assert summary["spent_usd"] + MA.worst_case_cost(last, HAIKU) > cap
    assert summary["stopped_by_cap"] and not summary["complete"]
    assert not summary["claims"]["allowed"] and summary["claims"]["significant"] == []
    row = summary["per_model"][HAIKU]
    assert not row["complete"] and row["all_trials"] is None
    assert row["statuses"]["not_run"] == 3 * 42 - len(client.requests)
    assert SONNET not in summary["per_model"]  # nothing was asked of the next model
    # The partial answers file holds only the cases that were asked.
    lines = (tmp_path / f"answers-{HAIKU}-trial1.jsonl").read_text().splitlines()
    assert len(lines) == len(client.requests)


def test_a_request_that_fails_without_usage_is_held_against_the_cap():
    budget = MA.Budget(1.0)
    client = FakeClient(lambda case_id, model, nth: ApiError())
    public = MR.presented()[0][1]
    outcome = MA.ModelAgent(OPUS, client, budget).answer_case(public)
    reserve = MA.worst_case_cost(MA.build_request(OPUS, public), OPUS)
    assert outcome.status == MA.ERROR and outcome.attempts == 2
    assert budget.spent == 0 and budget.unmeasured == pytest.approx(2 * reserve)
    # With too little left for one more worst case, nothing is sent.
    tight = MA.Budget(reserve * 0.99)
    idle = FakeClient()
    assert MA.ModelAgent(OPUS, idle, tight).answer_case(public).status == MA.NOT_RUN
    assert idle.requests == [] and tight.stopped


def test_the_worst_case_bounds_what_a_request_reporting_max_tokens_costs():
    for _, public in MR.presented():
        request = MA.build_request(OPUS, public)
        usage = {"input_tokens": MA.estimate_input_tokens(request),
                 "output_tokens": request["max_tokens"]}
        assert MA.cost(usage, OPUS) == pytest.approx(MA.worst_case_cost(request, OPUS))


# ---------------------------------------------------------------- the summary

def test_a_case_counts_only_if_it_passes_in_every_trial(tmp_path):
    flaky = ALL_CASES[5].id

    def behave(case_id, model, nth):
        if case_id == flaky and nth == 2:  # third trial
            return tool_response({"text": "", "citations": [], "abstained": False,
                                  "retrieved_ids": []})
        return None

    summary = valid(MR.run([HAIKU], 3, 5.0, tmp_path, FakeClient(behave)))
    row = summary["per_model"][HAIKU]
    assert row["all_trials"]["passed"] == 41 and row["any_trial"]["passed"] == 42
    assert row["spread"] == {"passed_by_trial": [42, 42, 41], "min": 41, "max": 42,
                             "mean": 125 / 3, "range": 1, "unstable_cases": 1}
    assert sum(m["total"] for m in row["by_mode"].values()) == 126
    assert sum(m["passed"] for m in row["by_mode"].values()) == 125
    assert row["budget_bound"]["total"] == 11 and row["not_budget_bound"]["total"] == 31
    assert summary["budget_bound_cases"] == 11


def test_over_refusal_and_gates_count_what_the_model_did(tmp_path):
    answerable = [c.id for c in ALL_CASES if not c.should_abstain]

    def behave(case_id, model, nth):
        if case_id in answerable[:4]:
            return tool_response({"text": "I cannot tell.", "citations": [], "abstained": True,
                                  "retrieved_ids": []})
        return None

    row = valid(MR.run([HAIKU], 1, 5.0, tmp_path, FakeClient(behave)))["per_model"][HAIKU]
    assert row["over_refusal"]["abstained"] == 4 and row["over_refusal"]["total"] == 39
    assert row["per_trial"][0]["over_refusal"]["abstained"] == 4
    assert row["gates"]["abstention"] == {"failed": 4, "applicable": 42}
    assert row["all_trials"]["passed"] == 38


def test_comparisons_pair_each_model_with_both_baselines_and_with_each_other(tmp_path):
    weak = {c.id for c in ALL_CASES[:30]}

    def behave(case_id, model, nth):
        if model == HAIKU and case_id in weak:
            return tool_response({"text": "", "citations": [], "abstained": False,
                                  "retrieved_ids": []})
        return None

    summary = valid(MR.run([HAIKU, SONNET], 1, 50.0, tmp_path, FakeClient(behave)))
    primary = {(r["model"], r["against"]): r for r in summary["comparisons"]["primary"]}
    assert set(primary) == {(m, b) for m in (HAIKU, SONNET) for b in ("reference", "overlap-document")}
    assert summary["baselines"]["reference"]["passed"] == 9
    assert summary["baselines"]["best_surface"]["passed"] == 14
    perfect = primary[(SONNET, "reference")]
    assert (perfect["gained"], perfect["lost"]) == (33, 0)
    # Holm over the four primary tests, in the order they are listed.
    rows = summary["comparisons"]["primary"]
    assert [r["p_holm"] for r in rows] == stats.holm([r["p_value"] for r in rows])
    assert any(r["p_holm"] > r["p_value"] for r in rows)
    (between,) = summary["comparisons"]["between_models"]
    assert (between["model"], between["against"]) == (SONNET, HAIKU)
    assert (between["gained"], between["lost"]) == (30, 0) and between["p_holm"] == between["p_value"]
    # No preregistration: nothing is claimed, however small the p.
    assert not summary["claims"]["allowed"] and summary["claims"]["significant"] == []


# ------------------------------------------------------------ preregistration

def test_the_committed_preregistration_matches_the_code_it_registers():
    prereg = MR.load_prereg(PREREG)
    assert prereg["sha256"] == hashlib.sha256(PREREG.read_bytes()).hexdigest()
    actual = MR.run_settings(list(MR.DEFAULT_MODELS), MR.DEFAULT_TRIALS, DEFAULT_SHUFFLE_SEED,
                             MR.baselines(DEFAULT_SHUFFLE_SEED)["best_surface_name"])
    assert MR.deviations(prereg, actual) == []
    assert prereg["comparisons"]["primary"]["size"] == 2 * len(MR.DEFAULT_MODELS)
    assert prereg["thresholds"]["alpha"] == 0.05


def test_the_preregistered_run_makes_claims_and_prints_the_hash(tmp_path):
    prereg = MR.load_prereg(PREREG)
    summary = valid(MR.run(list(MR.DEFAULT_MODELS), 3, 500.0, tmp_path, FakeClient(), prereg))
    assert summary["complete"] and summary["claims"] == {
        "allowed": True, "reason": None, "alpha": 0.05,
        "significant": [
            {"model": m, "against": b, "family": "primary"}
            for m in MR.DEFAULT_MODELS for b in ("reference", "overlap-document")
        ],
    }
    assert summary["prereg"]["sha256"] == hashlib.sha256(PREREG.read_bytes()).hexdigest()
    assert summary["prereg"]["deviations"] == []
    assert summary["prereg"]["sha256"] in MR.render_summary(summary)
    assert len(summary["comparisons"]["primary"]) == 6
    assert len(summary["comparisons"]["between_models"]) == 3


@pytest.mark.parametrize("models, trials, setting", [
    ([HAIKU, SONNET, OPUS], 1, "trials"),
    ([HAIKU], 3, "models"),
])
def test_a_run_that_deviates_withholds_its_claims(tmp_path, models, trials, setting):
    prereg = MR.load_prereg(PREREG)
    summary = valid(MR.run(models, trials, 500.0, tmp_path, FakeClient(), prereg))
    assert [d["setting"] for d in summary["prereg"]["deviations"]] == [setting]
    assert not summary["claims"]["allowed"] and setting in summary["claims"]["reason"]
    assert summary["claims"]["significant"] == []
    # The tests are still reported, as exploratory.
    assert summary["comparisons"]["primary"]
    assert "No claim is made" in MR.render_summary(summary)


def test_a_changed_prompt_is_a_deviation(tmp_path, monkeypatch):
    monkeypatch.setitem(MA.ANSWER_TOOL, "description", "Answer.")
    summary = MR.run(list(MR.DEFAULT_MODELS), 3, 500.0, tmp_path, FakeClient(), MR.load_prereg(PREREG))
    assert [d["setting"] for d in summary["prereg"]["deviations"]] == ["prompt_sha256"]
    assert not summary["claims"]["allowed"]


def test_too_many_request_errors_withhold_claims(tmp_path):
    broken = {c.id for c in ALL_CASES[:3]}  # 3 of 42 is above the 5% registered

    def behave(case_id, model, nth):
        return ApiError(529) if model == OPUS and case_id in broken else None

    summary = valid(MR.run(list(MR.DEFAULT_MODELS), 3, 500.0, tmp_path, FakeClient(behave),
                           MR.load_prereg(PREREG)))
    assert summary["complete"] and summary["prereg"]["deviations"] == []
    assert not summary["claims"]["allowed"] and OPUS in summary["claims"]["reason"]


def test_a_preregistration_missing_a_setting_is_refused(tmp_path):
    doc = json.loads(PREREG.read_text())
    del doc["settings"]["prompt_sha256"]
    path = tmp_path / "prereg.json"
    path.write_text(json.dumps(doc))
    with pytest.raises(MR.UsageError, match="prompt_sha256"):
        MR.load_prereg(path)


# ------------------------------------------------------ estimate and the CLI

def _no_client():
    raise AssertionError("the estimate must not build a client")


def test_estimate_builds_no_client_and_prices_every_first_request(tmp_path, capsys):
    code = MR.main(["--estimate", "--out", str(tmp_path)], client_factory=_no_client)
    assert code == 0
    est = json.loads((tmp_path / "estimate.json").read_text())
    requests = [MA.build_request(HAIKU, p) for _, p in MR.presented()]
    per_trial = sum(MA.estimate_input_tokens(r) for r in requests)
    for row in est["rows"]:
        assert row["calls"] == 126 and row["input_tokens"] == 3 * per_trial
        assert row["output_tokens"] == 126 * MR.ESTIMATE_OUTPUT_TOKENS
        assert row["usd"] == round(MA.cost(row, row["model"]), 4)
        assert row["ceiling_usd"] > row["usd"]
    assert est["total_usd"] == round(sum(r["usd"] for r in est["rows"]), 2)
    assert f"estimated total: ${est['total_usd']:.2f}" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == [tmp_path / "estimate.json"]


def test_the_estimate_is_above_the_characters_over_four_rule():
    """Deliberately high: more tokens than the usual four characters each."""
    for _, public in MR.presented():
        request = MA.build_request(HAIKU, public)
        chars = len(request["system"]) + len(request["messages"][0]["content"])
        assert MA.estimate_input_tokens(request) > chars / 4 * 1.35


def test_a_real_run_needs_a_cap_an_out_dir_and_a_key(tmp_path, monkeypatch, capsys):
    assert MR.main(["--out", str(tmp_path)], client_factory=_no_client) == 2
    assert MR.main(["--max-usd", "5"], client_factory=_no_client) == 2
    assert MR.main(["--max-usd", "5", "--out", str(tmp_path), "--models", "gpt-9"],
                   client_factory=_no_client) == 2
    pytest.importorskip("anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert MR.main(["--max-usd", "5", "--out", str(tmp_path)]) == 2
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


def test_main_exit_codes_follow_completeness_and_deviation(tmp_path, capsys):
    args = ["--max-usd", "500", "--prereg", str(PREREG)]
    assert MR.main([*args, "--out", str(tmp_path / "a")], client_factory=FakeClient) == 0
    assert MR.main([*args, "--trials", "1", "--out", str(tmp_path / "b")],
                   client_factory=FakeClient) == 1
    capped = ["--max-usd", "0.01", "--models", SONNET, "--out", str(tmp_path / "c")]
    assert MR.main(capped, client_factory=FakeClient) == 1
    valid(json.loads((tmp_path / "c" / "summary.json").read_text()))
    capsys.readouterr()


def test_the_workflow_starts_only_by_hand_on_a_hosted_runner_with_read_access():
    text = (ROOT / ".github" / "workflows" / "model-run.yml").read_text()
    body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    on = body.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert re.findall(r"^  (\w+):", on, flags=re.M) == ["workflow_dispatch"]
    assert re.findall(r"^      (\w+):$", on, flags=re.M) == ["max_usd", "models", "trials"]
    assert "pull_request" not in body and "push" not in body and "schedule" not in body
    assert re.search(r"^permissions:\n  contents: read\n", body, flags=re.M)
    assert re.findall(r"runs-on: (\S+)", body) == ["ubuntu-latest"]
    assert body.index("--estimate") < body.index("secrets.ANTHROPIC_API_KEY")
    assert "ANTHROPIC_API_KEY repository secret is not set" in body
    assert "actions/upload-artifact" in body
    # The secret is not in the environment of the step that only prices.
    estimate_step = body.split("Price the run")[1].split("- name:")[0]
    assert "secrets." not in estimate_step
