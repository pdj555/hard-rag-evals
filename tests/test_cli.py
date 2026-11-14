"""The command line: one JSON document per call, a committed schema, fixed exit codes."""
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from hard_rag_evals import CANARY, GRADER_VERSION, cli
from hard_rag_evals import report as R
from hard_rag_evals.failure_modes import ALL_CASES
from hard_rag_evals.runner import GATES

ROOT = Path(__file__).parent.parent
SCHEMA = R.load_schema()
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
GOLD = json.loads((ROOT / "tests" / "gold_answers.json").read_text())
GOLD.pop("_canary")


def run(capsys, *argv):
    """Exit code and stdout of one in-process call. Bad command lines raise
    SystemExit from argparse; that is an exit code like any other."""
    try:
        code = cli.main(list(argv))
    except SystemExit as exc:
        code = exc.code
    return code, capsys.readouterr().out


def run_json(capsys, *argv):
    code, out = run(capsys, *argv, "--json")
    document = json.loads(out)  # exactly one document, nothing else on stdout
    VALIDATOR.validate(document)
    return code, document


def answers_file(tmp_path, rows):
    path = tmp_path / "answers.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return str(path)


def gold_rows():
    return [{"case_id": cid, **g} for cid, g in GOLD.items()]


# ---- the schema ----


def test_committed_schema_is_a_valid_schema_and_matches_the_code():
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["$defs"]["gate"]["enum"] == list(GATES)
    assert SCHEMA["$defs"]["report"]["properties"]["schema_version"]["const"] == R.SCHEMA_VERSION
    committed = ROOT / "hard_rag_evals" / "schemas" / "output.schema.json"
    assert json.loads(committed.read_text()) == SCHEMA


def test_schema_rejects_a_report_that_drops_or_adds_a_field(capsys):
    _, report = run_json(capsys, "run", "--agent", "reference")
    for broken in (
        {k: v for k, v in report.items() if k != "grader_version"},
        {**report, "extra": 1},
        {**report, "summary": {**report["summary"], "ci95": [0.1]}},
        {**report, "results": [{**report["results"][0], "gates": {"made_up_gate": True}}]},
    ):
        with pytest.raises(jsonschema.ValidationError):
            VALIDATOR.validate(broken)


def test_schema_command_prints_the_schema(capsys):
    code, out = run(capsys, "schema")
    assert code == 0 and json.loads(out) == SCHEMA


# ---- list and show ----


def test_list_json(capsys):
    code, doc = run_json(capsys, "list")
    assert code == 0 and doc["kind"] == "case_list"
    assert [c["id"] for c in doc["cases"]] == [c.id for c in ALL_CASES]
    assert doc["canary"] == CANARY and doc["grader_version"] == GRADER_VERSION
    code, doc = run_json(capsys, "list", "--difficulty", "brutal", "--mode", "compositional")
    assert len(doc["cases"]) == 4


def test_show_gives_the_task_and_not_the_answer_key(capsys):
    code, doc = run_json(capsys, "show", "stale-medium")
    assert code == 0 and doc["kind"] == "case"
    case = next(c for c in ALL_CASES if c.id == "stale-medium")
    assert doc["case"]["query"] == case.query
    assert [d["id"] for d in doc["case"]["documents"]] == [d.id for d in case.corpus.documents]
    assert case.must_not_cite  # the case has a key worth hiding
    text = json.dumps(doc)
    for hidden in ("must_cite", "must_not_cite", "gold_doc_ids", "expected", "conflict_claims"):
        assert hidden not in text


def test_show_shuffle_seed_reorders_the_documents(capsys):
    _, plain = run_json(capsys, "show", "adversarial-brutal")
    _, shuffled = run_json(capsys, "show", "adversarial-brutal", "--shuffle-seed", "1")
    ids = lambda d: [x["id"] for x in d["case"]["documents"]]  # noqa: E731
    assert ids(plain) != ids(shuffled) and sorted(ids(plain)) == sorted(ids(shuffled))


# ---- run ----


def test_run_reference_json_report(capsys):
    code, doc = run_json(capsys, "run", "--agent", "reference")
    assert code == 1  # some cases fail
    assert doc["kind"] == "report" and doc["agent"] == "reference-agent"
    s = doc["summary"]
    assert (s["passed"], s["total"]) == (9, 42)
    assert s["ci95"] == pytest.approx([0.10296, 0.368116], abs=1e-6)
    assert {t: (v["passed"], v["total"]) for t, v in s["by_tier"].items()} == {
        "easy": (6, 12), "medium": (2, 12), "hard": (1, 13), "brutal": (0, 5),
    }
    assert s["gates"]["forbidden_citation"] == {"failed": 15, "applicable": 16}
    assert s["over_refusal"]["abstained"] == 0 and s["over_refusal"]["total"] == 39
    assert s["correct_abstention"]["total"] == 3
    assert len(doc["results"]) == 42
    assert all(r["grader_version"] == GRADER_VERSION for r in doc["results"])
    assert all(r["passed"] == (not r["failed_gates"]) for r in doc["results"])
    assert doc["config"]["source"] == "built_in_agent" and doc["config"]["shuffle_seed"] is None


def test_run_a_gamer_by_name_with_filters_and_seed(capsys):
    code, doc = run_json(
        capsys, "run", "--agent", "always-abstain", "--mode", "unanswerable", "--shuffle-seed", "7"
    )
    assert code == 0  # every graded case passed
    assert doc["summary"]["passed"] == doc["summary"]["total"] == 3
    assert doc["summary"]["over_refusal"] is None
    assert doc["config"] == {
        "source": "built_in_agent", "difficulty": None, "modes": ["unanswerable"],
        "shuffle_seed": 7, "missing_case_ids": [],
    }


def test_every_built_in_agent_is_runnable_by_name(capsys):
    assert set(cli.AGENTS) == {
        "reference", "hedger", "cite-everything", "always-abstain", "number-spray",
        "total-guess", "query-echo",
    }
    for name in cli.AGENTS:
        code, doc = run_json(capsys, "run", "--agent", name, "--difficulty", "easy")
        assert code in (0, 1) and doc["summary"]["total"] == 12


def test_run_without_json_prints_the_markdown_report(capsys):
    code, out = run(capsys, "run", "--agent", "reference")
    assert code == 1
    assert out.startswith("# Eval report: reference-agent")


# ---- grade ----


def test_grade_gold_answers_file_passes_everything(capsys, tmp_path):
    code, doc = run_json(capsys, "grade", answers_file(tmp_path, gold_rows()), "--agent-name", "gold")
    assert code == 0
    assert doc["agent"] == "gold" and doc["config"]["source"] == "answers_file"
    assert doc["summary"]["passed"] == doc["summary"]["total"] == 42
    assert doc["config"]["missing_case_ids"] == []


def test_answer_lines_validate_against_the_schema():
    answer = jsonschema.Draft202012Validator({**SCHEMA["$defs"]["answer"], "$defs": SCHEMA["$defs"]})
    for row in gold_rows():
        answer.validate(row)


def test_grade_exits_1_when_an_answer_fails(capsys, tmp_path):
    rows = gold_rows()
    rows[0] = {**rows[0], "citations": rows[0]["citations"] + ["doc-not-in-corpus"]}
    code, doc = run_json(capsys, "grade", answers_file(tmp_path, rows))
    assert code == 1
    assert doc["summary"]["passed"] == 41
    failed = [r for r in doc["results"] if not r["passed"]]
    assert [r["failed_gates"] for r in failed] == [["unknown_citation"]]


def test_grade_reads_stdin(capsys, monkeypatch, tmp_path):
    text = Path(answers_file(tmp_path, gold_rows())).read_text()
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(text))
    code, doc = run_json(capsys, "grade", "-")
    assert code == 0 and doc["summary"]["total"] == 42


def test_grade_missing_cases_is_a_usage_error_unless_partial_is_allowed(capsys, tmp_path):
    path = answers_file(tmp_path, gold_rows()[:5])
    code, doc = run_json(capsys, "grade", path)
    assert code == 2 and doc["kind"] == "error"
    assert "37 of 42 cases have no answer" in doc["error"]["message"]
    code, doc = run_json(capsys, "grade", path, "--allow-partial")
    assert code == 0
    assert doc["summary"]["total"] == 5 and len(doc["config"]["missing_case_ids"]) == 37


@pytest.mark.parametrize(
    "line,complaint",
    [
        ("not json", "not valid JSON"),
        ("[1, 2]", "expected a JSON object"),
        ('{"text": "x"}', "'case_id' is required"),
        ('{"case_id": "stale-easy"}', "'text' is required"),
        ('{"case_id": "stale-easy", "text": "x", "citation": ["a"]}', "unknown keys ['citation']"),
        ('{"case_id": "stale-easy", "text": "x", "citations": "doc-a"}', "must be a list of strings"),
        ('{"case_id": "stale-easy", "text": "x", "abstained": "no"}', "must be true or false"),
        ('{"case_id": "no-such-case", "text": "x"}', "unknown case ids"),
    ],
)
def test_grade_malformed_answers_are_usage_errors(capsys, tmp_path, line, complaint):
    path = tmp_path / "bad.jsonl"
    path.write_text(line + "\n")
    code, doc = run_json(capsys, "grade", str(path), "--allow-partial")
    assert code == 2 and doc["kind"] == "error"
    assert complaint in doc["error"]["message"]


def test_grade_duplicate_empty_and_unreadable_files(capsys, tmp_path):
    row = json.dumps(gold_rows()[0])
    dup = tmp_path / "dup.jsonl"
    dup.write_text(row + "\n" + row + "\n")
    code, doc = run_json(capsys, "grade", str(dup), "--allow-partial")
    assert code == 2 and "answered more than once" in doc["error"]["message"]
    empty = tmp_path / "empty.jsonl"
    empty.write_text("\n")
    code, doc = run_json(capsys, "grade", str(empty), "--allow-partial")
    assert code == 2 and "no cases were graded" in doc["error"]["message"]
    code, doc = run_json(capsys, "grade", str(tmp_path / "missing.jsonl"))
    assert code == 2 and "cannot read" in doc["error"]["message"]


# ---- exit codes ----


def test_usage_errors_exit_2_and_still_print_one_document_with_json(capsys):
    for argv in (["run", "--agent", "nobody"], ["show", "no-such-case"], ["run"], ["frobnicate"]):
        code, doc = run_json(capsys, *argv)
        assert code == 2 and doc["kind"] == "error" and doc["error"]["code"] == "usage"
    code, out = run(capsys, "show", "no-such-case")
    assert code == 2 and out == ""  # without --json, errors go to stderr only


def test_internal_error_exits_3_not_1(capsys, monkeypatch):
    def boom(args):
        raise RuntimeError("a bug")

    monkeypatch.setitem(cli._COMMANDS, "list", boom)
    code, out = run(capsys, "list")
    assert code == 3 and out == ""


def test_exit_codes_through_a_real_process(tmp_path):
    def call(*argv):
        proc = subprocess.run(
            [sys.executable, "-m", "hard_rag_evals", *argv], capture_output=True, text=True, cwd=tmp_path
        )
        return proc.returncode, proc.stdout

    code, out = call("list", "--json")
    assert code == 0 and json.loads(out)["kind"] == "case_list"
    code, out = call("run", "--agent", "reference", "--json")
    assert code == 1
    VALIDATOR.validate(json.loads(out))
    code, out = call("grade", answers_file(tmp_path, gold_rows()), "--json")
    assert code == 0
    code, out = call("run", "--agent", "nobody", "--json")
    assert code == 2 and json.loads(out)["kind"] == "error"


def test_console_script_is_declared():
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert 'hard-rag-evals = "hard_rag_evals.cli:main"' in pyproject
    assert '"schemas/*.json"' in pyproject


def test_mcp_subcommand_without_the_extra_is_a_usage_error(capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "hard_rag_evals.mcp_server", None)  # import now fails
    code, out = run(capsys, "mcp")
    assert code == 2
