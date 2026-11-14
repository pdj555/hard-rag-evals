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
hard-rag-evals list --json                         # every case: id, tier, mode, question
hard-rag-evals show numeric-easy --json            # one case: question, documents, budget
hard-rag-evals run --agent reference --json        # run a built-in agent and grade it
hard-rag-evals grade answers.jsonl --json          # grade answers from any agent
hard-rag-evals schema                              # JSON Schema for all --json output
hard-rag-evals mcp                                 # MCP server on stdio
```

`python -m hard_rag_evals` is the same command. Built-in agents for `run --agent`: `reference`, `hedger`, `cite-everything`, `always-abstain`, `number-spray`, `total-guess`, `query-echo`.

Answers file for `grade`: JSON Lines, one object per case.

```json
{"case_id": "stale-easy", "text": "The API rate limit is 1000 requests per hour.", "citations": ["doc-ratelimit-new"], "abstained": false}
```

`case_id` and `text` are required. `citations`, `abstained` and `retrieved_ids` are optional. Any other key is an error. Every case must be answered unless `--allow-partial` is passed. `-` reads stdin.

Exit codes:

| code | meaning |
| ---- | ------- |
| 0 | the command worked and every graded case passed |
| 1 | the command worked and at least one graded case failed |
| 2 | usage error: bad arguments, unknown case, malformed or incomplete answers file |
| 3 | internal error, a bug in this package |

With `--json`, stdout holds exactly one JSON document, also on a usage error (`"kind": "error"`). It validates against `hard_rag_evals/schemas/output.schema.json`.

MCP tools: `list_cases(difficulty?, mode?)`, `get_case(case_id)`, `grade_answer(case_id, text, citations?, abstained?, retrieved_ids?, explain?)`.

## Rules for changes

- The grader decides a pass in `runner.grade()`, from the gates in `runner.GATES`. Scores are reported and never decide a pass.
- A change that can alter any verdict or score bumps `GRADER_VERSION` in `hard_rag_evals/provenance.py`. Never change `CANARY_GUID`.
- Every fixture carries the canary under `"canary"`; a fixture without it does not load.
- `show`, `get_case` and `report.public_case` must never expose a case's gates, gold ids or expected answer.
- `tests/test_gamers.py`, `tests/test_gates.py` and `tests/test_stats.py` pin exact counts. If a change moves one, update the pin and the number in `README.md` and `docs/` in the same commit, from what the code prints.
- Removing or renaming a field of the `--json` output bumps `SCHEMA_VERSION` in `hard_rag_evals/report.py` and updates the schema file. Adding a field updates the schema only.
- No model calls, API keys or network access anywhere in the package or its tests.
- CI runs on GitHub-hosted runners (`ubuntu-latest`).
