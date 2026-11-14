"""Canary in every fixture and export row; grader version in every result."""
import importlib.util
import json
import re
from dataclasses import asdict, replace
from importlib import resources
from pathlib import Path

import pytest

from hard_rag_evals import (
    CANARY,
    DATASET_VERSION,
    GRADER_VERSION,
    Answer,
    Corpus,
    RetrievalBudget,
    failure_modes,
)
from hard_rag_evals.failure_modes import ALL_CASES
from hard_rag_evals.provenance import CANARY_GUID, EXPECTED_DATASET_VERSION, dataset_version
from hard_rag_evals.reference_agent import ReferenceAgent
from hard_rag_evals.runner import grade, render_markdown, run_suite

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("export_dataset", ROOT / "scripts" / "export_dataset.py")
export = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export)


def test_canary_is_a_guid_in_a_plain_sentence():
    assert re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", CANARY_GUID)
    assert CANARY_GUID in CANARY
    assert "SHOULD NEVER APPEAR IN TRAINING CORPORA" in CANARY


def test_every_fixture_file_carries_the_canary():
    fixtures = [
        p for p in resources.files("hard_rag_evals").joinpath("fixtures").iterdir()
        if p.name.endswith(".json")
    ]
    assert len(fixtures) == 42
    for path in fixtures:
        assert json.loads(path.read_text())["canary"] == CANARY, path.name


def test_every_case_and_the_gold_answers_carry_the_canary():
    assert len(ALL_CASES) == 42
    assert all(c.canary == CANARY for c in ALL_CASES)
    assert json.loads((ROOT / "tests" / "gold_answers.json").read_text())["_canary"] == CANARY


def test_a_fixture_without_the_canary_does_not_load(monkeypatch, tmp_path):
    (tmp_path / "bare.json").write_text(json.dumps({"query": "q", "documents": []}))
    (tmp_path / "wrong.json").write_text(json.dumps({"canary": "something else", "query": "q"}))
    monkeypatch.setattr(failure_modes, "_FIXTURE_DIR", tmp_path)
    for name in ("bare", "wrong"):
        with pytest.raises(ValueError, match="canary"):
            failure_modes._load_fixture(name)


def test_export_carries_the_canary_and_grader_version_on_every_row(tmp_path, capsys):
    rows = export.rows()
    assert len(rows) == 42
    assert all(r["canary"] == CANARY and r["grader_version"] == GRADER_VERSION for r in rows)
    assert all(r["dataset_version"] == DATASET_VERSION for r in rows)
    export.main(str(tmp_path))
    lines = (tmp_path / "cases.jsonl").read_text().splitlines()
    assert len(lines) == 42
    assert all(CANARY_GUID in line for line in lines)
    assert all(json.loads(line)["grader_version"] == GRADER_VERSION for line in lines)
    assert f"grader version {GRADER_VERSION}" in capsys.readouterr().out


def test_every_result_records_the_grader_version():
    assert re.fullmatch(r"\d+\.\d+\.\d+", GRADER_VERSION)
    results = run_suite(ReferenceAgent())
    assert all(r.grader_version == GRADER_VERSION for r in results)
    assert grade(ALL_CASES[0], Answer(text="x")).grader_version == GRADER_VERSION
    report = render_markdown("reference-agent", results)
    assert f"Grader version {GRADER_VERSION}, dataset version {DATASET_VERSION[:12]}." in report


def _version(cases):
    return dataset_version([asdict(c) for c in cases])


def test_dataset_version_is_computed_from_the_cases_that_were_built():
    assert re.fullmatch(r"[0-9a-f]{64}", DATASET_VERSION)
    assert DATASET_VERSION == failure_modes.DATASET_VERSION == _version(ALL_CASES)
    assert _version(list(reversed(ALL_CASES))) == DATASET_VERSION  # order of building is not data


@pytest.mark.parametrize(
    "change",
    [
        lambda c: replace(c, budget=RetrievalBudget(max_docs=c.budget.max_docs + 1, max_chars=c.budget.max_chars)),
        lambda c: replace(c, budget=RetrievalBudget(max_docs=c.budget.max_docs, max_chars=c.budget.max_chars + 1)),
        lambda c: replace(c, difficulty="brutal"),
        lambda c: replace(c, mode="renamed_mode"),
        lambda c: replace(c, id=c.id + "-x"),
        lambda c: replace(c, query=c.query + " "),
        lambda c: replace(c, must_cite=()),
        lambda c: replace(c, corpus=Corpus(documents=c.corpus.documents[::-1] + c.corpus.documents[:1])),
        lambda c: replace(c, corpus=Corpus(documents=(replace(c.corpus.documents[0], published="1999-01-01"),) + c.corpus.documents[1:])),
    ],
)
def test_dataset_version_moves_with_any_field_grading_or_the_public_view_uses(change):
    cases = list(ALL_CASES)
    cases[0] = change(cases[0])
    assert _version(cases) != DATASET_VERSION


def test_changing_a_budget_in_a_python_builder_changes_the_dataset_version(monkeypatch):
    # Budgets live in failure_modes/*.py, not in the fixture files. Rebuild the
    # suite with one builder's max_docs changed, as an edit to that file would.
    from hard_rag_evals.failure_modes import retrieval_misses

    fixtures_before = {
        p.name: p.read_bytes()
        for p in resources.files("hard_rag_evals").joinpath("fixtures").iterdir()
        if p.name.endswith(".json")
    }
    assert retrieval_misses._BUDGET.max_docs == 2
    monkeypatch.setattr(retrieval_misses, "_BUDGET", RetrievalBudget(max_docs=3, max_chars=8000))
    rebuilt = [m.build_easy() for m in failure_modes._TIERED] + [m.build() for m in failure_modes._TIERED]
    rebuilt += [m.build_hard() for m in failure_modes._TIERED]
    rebuilt += failure_modes.adversarial.build_all() + failure_modes.compositional.build_all()
    assert len(rebuilt) == 42
    changed = [a.id for a, b in zip(rebuilt, ALL_CASES) if a != b]
    assert changed and all(i.startswith("retrieval-miss") for i in changed)
    assert _version(rebuilt) != DATASET_VERSION
    fixtures_after = {
        p.name: p.read_bytes()
        for p in resources.files("hard_rag_evals").joinpath("fixtures").iterdir()
        if p.name.endswith(".json")
    }
    assert fixtures_before == fixtures_after  # no fixture byte changed, and the version still moved


def test_docs_were_written_against_this_dataset_version():
    assert DATASET_VERSION == EXPECTED_DATASET_VERSION, (
        "a case changed: the numbers in README.md and docs/ may be stale. Re-run "
        "examples/demo.py and examples/grader_attacks.py, update the docs, then set "
        f"EXPECTED_DATASET_VERSION in provenance.py to {DATASET_VERSION}"
    )


def test_every_result_and_document_records_the_dataset_version():
    from hard_rag_evals import report as R

    results = run_suite(ReferenceAgent())
    assert all(r.dataset_version == DATASET_VERSION for r in results)
    document = R.report_document("reference-agent", results, {})
    assert document["dataset_version"] == DATASET_VERSION
    assert all(r["dataset_version"] == DATASET_VERSION for r in document["results"])
