# AGENTS.md

Instructions for coding agents working in this repository. `README.md` says what the suite found; `docs/guide.md` says how grading works.

## Setup

```bash
python -m pip install -e '.[dev,mcp]'
```

Python 3.10 or newer. The package has no runtime dependencies. `dev` adds pytest and jsonschema; `mcp` adds the MCP SDK (2.x), needed only for `hard-rag-evals mcp` and `tests/test_mcp.py`.

## Check your work

```bash
python -m pytest
```

Run it before saying a change is done. It takes a few seconds and makes no network or model calls. There is no linter configured in this repository.

After changing the grader, a fixture, or an agent, regenerate the committed example reports and read the diff:

```bash
python examples/demo.py
python examples/grader_attacks.py
```

## Use the suite

```bash
hard-rag-evals list --json                         # every case, public view: opaque id, tier, question
hard-rag-evals show c-03854abeb347 --json          # one case: question, documents, budget
hard-rag-evals run --agent reference --json        # run a built-in agent and grade it
hard-rag-evals grade answers.jsonl --json          # grade answers from any agent
hard-rag-evals schema                              # JSON Schema for all --json output
hard-rag-evals mcp                                 # MCP server on stdio, for an agent under test
hard-rag-evals --version                           # package, grader and dataset versions
```

`python -m hard_rag_evals` is the same command. Built-in agents for `run --agent`: `reference`, `fabricating`, `hedger`, `cite-everything`, `always-abstain`, `number-spray`, `total-guess`, `mean-guess`, `sum-minus-largest`, `query-echo`, `first-document`, `overlap-document`, `greatest-id-document`, `newest-document`, `shortest-document`.

`run` and `show` shuffle each case's documents with seed 2026 and record the seed. `--shuffle-seed N` picks another. `--fixture-order` keeps the order in the fixture, which lists a required document first in 33 of 39 cases; use it only to reproduce that leak. Flags cannot be abbreviated.

`list` and `show` print the public view: opaque ids, no failure mode, sorted by id. `--dev` adds the descriptive id and the mode, lets `show` take a descriptive id, and lets `list` filter with `--mode`. Do not give `--dev` output, or a `run` or `grade` report, to an agent whose score you want to trust.

Answers file for `grade`: JSON Lines in UTF-8, one object per case. A file and stdin are decoded the same way, strictly. `case_id` is a public id or a descriptive id.

```json
{"case_id": "c-03854abeb347", "text": "Start a return in the warranty portal.", "citations": ["doc-id"], "abstained": false}
```

`case_id` and `text` are required. `citations`, `abstained` and `retrieved_ids` are optional. Any other key is an error, and so is a key given twice in one object. Every case must be answered unless `--allow-partial` is passed; a partial report says "N of 42 cases graded", lists the cases not graded, and exits 1 even when everything graded passed. The same holds for `run` with `--difficulty` or `--mode`. Exit 0 means the whole suite passed. `-` reads stdin.

Exit codes:

| code | meaning |
| ---- | ------- |
| 0 | the command worked, all 42 cases were graded, and all passed |
| 1 | the command worked, and a graded case failed or fewer than 42 cases were graded |
| 2 | usage error: bad arguments, unknown case, malformed or incomplete answers file |
| 3 | internal error (a bug in this package), or the output could not be written |

With `--json`, stdout holds exactly one JSON document that validates against `hard_rag_evals/schemas/output.schema.json`. That holds on failure too: a usage error prints `"kind": "error"` with `"code": "usage"`, and an internal error prints the same with `"code": "internal"` and puts the traceback on stderr. Without `--json`, errors go to stderr only.

Malformed input is always exit 2, never a traceback: invalid UTF-8, invalid JSON, JSON nested too deeply, an integer too long to convert, text that is not valid Unicode, duplicate keys.

Output failures:

- The reader of a pipe went away (`hard-rag-evals list | head -1`, EPIPE): no message, and the exit code is the one the command would have returned, 0 or 1.
- Any other failure to write stdout (disk full, stdout closed or invalid): one line on stderr if stderr works, no traceback, exit 3. That includes a usage error whose `--json` document could not be written.

MCP tools on the default server:

- `list_cases(difficulty?)` and `get_case(case_id)`: the public view. `get_case` takes public ids only and lists documents shuffled with seed 2026.
- `grade_submission(answers)`: grades a submission that answers all 42 cases and returns one overall count with an interval. No per-tier split, nothing about a single case. A submission that leaves a case out is refused. A server process grades one submission, and concurrent calls do not get around that.

`hard-rag-evals mcp --dev` adds `grade_answer(case_id, text, citations?, abstained?, retrieved_ids?)`, which returns one case's gates and notes, shows descriptive ids and modes, and lifts the one-submission limit. It hands out the answer key a probe at a time. A score from a `--dev` server means nothing.

## Rules for changes

- The grader decides a pass in `runner.grade()`, from the gates in `runner.GATES`. The budget gate reads `retrieved_ids`: report every document your agent read there, or your result on the 11 budget-bound cases is not comparable to anyone's. Scores are reported and never decide a pass.
- A change that can alter any verdict or score bumps `GRADER_VERSION` in `hard_rag_evals/provenance.py`. Never change `CANARY_GUID`.
- `DATASET_VERSION` is computed at import from the cases as built: fixture content plus the ids, tiers, modes and budgets set in `failure_modes/*.py`. A change to any of them changes it, and `tests/test_provenance.py` fails until the docs are brought up to date and `EXPECTED_DATASET_VERSION` in `provenance.py` is set to the new value. Published cases are not edited to close a grader hole; fix the grader or the harness.
- Never show an agent documents in fixture order by default. `run_suite`, `show` and `get_case` shuffle; keep it that way.
- Every fixture carries the canary under `"canary"`; a fixture without it does not load.
- The public view (`list`, `show`, `list_cases`, `get_case`, `report.public_case`) must never expose a case's failure mode, descriptive id, gates, gold ids or expected answer. The default MCP server must never return anything about a single case's grade. `tests/test_mcp.py` and `tests/test_cli.py` pin both.
- `tests/test_gamers.py`, `tests/test_gates.py`, `tests/test_stats.py` and `tests/test_order.py` pin exact counts. If a change moves one, update the pin and the number in `README.md` and `docs/` in the same commit, from what the code prints.
- Removing or renaming a field of the `--json` output bumps `SCHEMA_VERSION` in `hard_rag_evals/report.py` and updates the schema file. Adding a field updates the schema only.
- No model calls, API keys or network access anywhere in the package or its tests.
- CI runs on GitHub-hosted runners (`ubuntu-latest`).
