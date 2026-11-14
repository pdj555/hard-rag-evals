"""Write the suite as JSON Lines, one case per line, for the Hugging Face dataset.

Every field comes from the fixtures and tests/gold_answers.json at the current
commit, so the published dataset can be rebuilt and diffed against the repo.

Usage: python scripts/export_dataset.py OUT_DIR
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hard_rag_evals.failure_modes import ALL_CASES, DATASET_VERSION  # noqa: E402
from hard_rag_evals.provenance import CANARY, GRADER_VERSION  # noqa: E402


def rows() -> list[dict]:
    gold = json.loads((ROOT / "tests" / "gold_answers.json").read_text())
    out = []
    for case in ALL_CASES:
        row = asdict(case)
        row["corpus"] = {"documents": [asdict(d) for d in case.corpus.documents]}
        row["reference_answer"] = gold[case.id]
        # Every row carries the canary and the grader version on its own, so a
        # single line lifted out of the file can still be traced and filtered.
        if row["canary"] != CANARY:
            raise ValueError(f"case {case.id} does not carry the canary")
        row["grader_version"] = GRADER_VERSION
        row["dataset_version"] = DATASET_VERSION
        out.append(row)
    return out


def main(out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows()]
    (out / "cases.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    print(
        f"wrote {len(lines)} cases to {out / 'cases.jsonl'} from commit {commit or 'unknown'}, "
        f"grader version {GRADER_VERSION}, dataset version {DATASET_VERSION}"
    )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dist/dataset")
