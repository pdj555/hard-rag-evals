"""Canary in every fixture and export row; grader version in every result."""
import importlib.util
import json
import re
from importlib import resources
from pathlib import Path

import pytest

from hard_rag_evals import CANARY, DATASET_VERSION, GRADER_VERSION, Answer, failure_modes
from hard_rag_evals.failure_modes import ALL_CASES
from hard_rag_evals.provenance import CANARY_GUID, compute_dataset_version
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


def test_committed_dataset_version_is_the_hash_of_the_fixtures():
    assert re.fullmatch(r"[0-9a-f]{64}", DATASET_VERSION)
    assert DATASET_VERSION == compute_dataset_version()


def test_dataset_version_moves_when_any_fixture_byte_or_name_changes(monkeypatch, tmp_path):
    from hard_rag_evals import provenance

    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "a.json").write_text("{}")
    (tmp_path / "fixtures" / "notes.txt").write_text("not a fixture")
    monkeypatch.setattr(provenance.resources, "files", lambda _: tmp_path)
    first = provenance.compute_dataset_version()
    (tmp_path / "fixtures" / "notes.txt").write_text("still not a fixture")
    assert provenance.compute_dataset_version() == first
    (tmp_path / "fixtures" / "a.json").write_text("{ }")
    second = provenance.compute_dataset_version()
    assert second != first
    (tmp_path / "fixtures" / "a.json").rename(tmp_path / "fixtures" / "b.json")
    assert provenance.compute_dataset_version() not in (first, second)


def test_every_result_and_document_records_the_dataset_version():
    from hard_rag_evals import report as R

    results = run_suite(ReferenceAgent())
    assert all(r.dataset_version == DATASET_VERSION for r in results)
    document = R.report_document("reference-agent", results, {})
    assert document["dataset_version"] == DATASET_VERSION
    assert all(r["dataset_version"] == DATASET_VERSION for r in document["results"])
