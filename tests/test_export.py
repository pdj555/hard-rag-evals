"""The exported dataset is the suite: same cases, and every reference answer passes."""
import importlib.util
from pathlib import Path

from hard_rag_evals import Answer
from hard_rag_evals.failure_modes import ALL_CASES
from hard_rag_evals.runner import grade

_spec = importlib.util.spec_from_file_location(
    "export_dataset", Path(__file__).parent.parent / "scripts" / "export_dataset.py"
)
export = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export)


def test_export_has_every_case_with_a_passing_reference_answer():
    rows = export.rows()
    cases = {c.id: c for c in ALL_CASES}
    assert [r["id"] for r in rows] == [c.id for c in ALL_CASES]
    for row in rows:
        ref = row["reference_answer"]
        answer = Answer(text=ref["text"], citations=list(ref["citations"]), abstained=ref["abstained"])
        assert grade(cases[row["id"]], answer).passed, row["id"]
        assert {d["id"] for d in row["corpus"]["documents"]} == cases[row["id"]].corpus.ids
