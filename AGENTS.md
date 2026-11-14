# AGENTS.md

Instructions for coding agents working in this repository. `README.md` says what the suite found; `docs/guide.md` says how grading works.

## Setup

```bash
python -m pip install -e '.[dev,mcp,models]'
```

Python 3.13 or newer. The package has no runtime dependencies. `dev` adds pytest, jsonschema and ruff; `mcp` adds the MCP SDK (2.x), needed only for `hard-rag-evals mcp` and `tests/test_mcp.py`. `models` adds the Anthropic SDK, needed only for a real run of `scripts/model_run.py`; its tests use a fake client.

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

`python -m hard_rag_evals` is the same command. Built-in agents for `run --agent`: `reference`, `fabricating`, `hedger`, `cite-everything`, `always-abstain`, `number-spray`, `total-guess`, `mean-guess`, `sum-minus-largest`, `query-echo`, `budget-smuggler`, `first-document`, `overlap-document`, `greatest-id-document`, `newest-document`, `shortest-document`.

`run` and `show` shuffle each case's documents with seed 2026 and record the seed. `--shuffle-seed N` picks another. `--fixture-order` keeps the order in the fixture, which lists a required document first in 33 of 39 cases; use it only to reproduce that leak. Flags cannot be abbreviated.

`list` and `show` print the public view: opaque ids, no failure mode, sorted by id. `--dev` adds the descriptive id and the mode, lets `show` take a descriptive id, and lets `list` filter with `--mode`. Do not give `--dev` output, or a `run` or `grade` report, to an agent whose score you want to trust.

Answers file for `grade`: JSON Lines in UTF-8, one object per case. A file and stdin are decoded the same way, strictly. `case_id` is a public id or a descriptive id.

```json
{"case_id": "c-03854abeb347", "text": "Start a return in the warranty portal.", "citations": ["doc-id"], "abstained": false}
```

`case_id` and `text` are required. `citations`, `abstained` and `retrieved_ids` are optional, but every citation of a document in the case must also be listed in `retrieved_ids`, or the case fails. Any other key is an error, and so is a key given twice in one object. Every case must be answered unless `--allow-partial` is passed; a partial report says "N of 42 cases graded", lists the cases not graded, and exits 1 even when everything graded passed. The same holds for `run` with `--difficulty` or `--mode`. Exit 0 means the whole suite passed. `-` reads stdin.

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

## Run a model

```bash
python scripts/model_run.py --estimate --prereg docs/prereg/model-run-1.json    # no calls, no key
gh workflow run model-run.yml -f max_usd=10 -f models=claude-haiku-5-5,claude-sonnet-5-5,claude-opus-5-5 -f trials=3
```

The second command spends money and is the owner's to start. It is `workflow_dispatch` only and reads the `ANTHROPIC_API_KEY` repository secret. The same run locally is `python scripts/model_run.py --max-usd 10 --out OUT_DIR --prereg docs/prereg/model-run-1.json`.

The estimate for the three models at 3 trials is $12.88: $0.21 for Haiku 5.5, $4.22 for Sonnet 5.5, $8.44 for Opus 5.5, at list prices. It assumes 2.5 characters per token plus 700 tokens per request for input, 3,000 output tokens per call, and one attempt per case. None of those figures has been checked against the API, because no call has been made. The ceiling, `max_tokens` of output on both attempts of every case, is $65.66. The estimate is above the workflow's default cap of $10; a run that reaches its cap stops, is marked incomplete and makes no claim, so raise `max_usd` or expect Opus 5.5 to be cut short if the estimate holds.

- The cap is checked before every request: a request is sent only if the spend so far plus the most that request can cost fits under `--max-usd`. Spend is measured from the usage the API returns.
- Each model answers all 42 cases in every trial from the public view, shuffled with seed 2026, with one `submit_answer` tool call. The prompt is `hard_rag_evals/prompts/model_agent_system.txt`; effort is pinned to medium; temperature is not sent.
- A refusal, a reply with no usable tool call after one retry, and a request that fails after one retry are each written as an empty answer and counted as failed. A request the API rejects outright (HTTP 400, 401, 403, 404) stops the run.
- The out directory holds `answers-MODEL-trialN.jsonl` (the file `hard-rag-evals grade` takes), the grader's report for each, `calls-MODEL-trialN.jsonl`, `summary.json` (schema: `hard_rag_evals/schemas/model_run.schema.json`) and `summary.md`.
- A case counts as passed only if it passed in every trial. `summary.json` prints the preregistration's sha256 and withholds every claim when the run deviates from it, is incomplete, or has request errors on more than 5% of a model's cases.
- The model is shown every document, so on the 11 cases whose corpus exceeds the retrieval budget it is not doing the reference agent's task. The summary reports those 11 and the other 31 separately.

## Rules for changes

- The grader decides a pass in `runner.grade()`, from the gates in `runner.GATES`. The budget gate reads `retrieved_ids`: report every document your agent read there, or your result on the 11 budget-bound cases is not comparable to anyone's. The unretrieved citation gate fails a citation that is not in `retrieved_ids`. Scores are reported and never decide a pass.
- A change that can alter any verdict or score bumps `GRADER_VERSION` in `hard_rag_evals/provenance.py`. Never change `CANARY_GUID`.
- `DATASET_VERSION` is computed at import from the cases as built: fixture content plus the ids, tiers, modes and budgets set in `failure_modes/*.py`. A change to any of them changes it, and `tests/test_provenance.py` fails until the docs are brought up to date and `EXPECTED_DATASET_VERSION` in `provenance.py` is set to the new value. Published cases are not edited to close a grader hole; fix the grader or the harness.
- Never show an agent documents in fixture order by default. `run_suite`, `show` and `get_case` shuffle; keep it that way.
- Every fixture carries the canary under `"canary"`; a fixture without it does not load.
- The public view (`list`, `show`, `list_cases`, `get_case`, `report.public_case`) must never expose a case's failure mode, descriptive id, gates, gold ids or expected answer. The default MCP server must never return anything about a single case's grade. `tests/test_mcp.py` and `tests/test_cli.py` pin both.
- `tests/test_gamers.py`, `tests/test_gates.py`, `tests/test_stats.py` and `tests/test_order.py` pin exact counts. If a change moves one, update the pin and the number in `README.md` and `docs/` in the same commit, from what the code prints.
- Removing or renaming a field of the `--json` output bumps `SCHEMA_VERSION` in `hard_rag_evals/report.py` and updates the schema file. Adding a field updates the schema only.
- No model calls, API keys or network access anywhere in the tests, the CLI or the grader. `hard_rag_evals/model_agent.py` is the one module that can reach a model, and only through a client it is handed; `scripts/model_run.py` builds that client, and only without `--estimate`.
- A change to the system prompt, the answer tool, or a setting in `model_agent.SETTINGS` changes what a model run measures. `tests/test_model_run.py` fails until `docs/prereg/model-run-1.json` matches; once a run has been made against a preregistration, write a new one instead of editing it.
- CI runs on GitHub-hosted runners (`ubuntu-latest`).
