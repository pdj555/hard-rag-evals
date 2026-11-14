# Guide

What this repo found is in the [README](../README.md). The full experiment is in the [research summary](research.md). This guide covers how a case is built, how grading runs, and what the scores do and do not decide.

## A case

Each case is one JSON fixture in `hard_rag_evals/fixtures/`, built by a module in `hard_rag_evals/failure_modes/`. The registry in `failure_modes/__init__.py` assembles all 42 cases as ALL_CASES: 12 modes at easy, medium, and hard, plus adversarial retrieval (2 cases) and compositional (4).

A fixture holds:

- A query and a corpus of short documents, each with an id, a source, and a published date.
- A retrieval budget: how many documents, and how many characters, the agent may pull.
- The gates for the case: required citations (`must_cite`), forbidden citations (`must_not_cite`), the two conflicting claims (`conflict_claims`), an expected number with a tolerance, an order pair, forbidden phrases, and an abstain flag for unanswerable cases.
- An "expected" answer in prose, and the gold document ids. The grader never reads the prose; the gold ids feed only the retrieval recall score.

## How grading runs

`runner.grade()` is all or nothing. Fail any gate and the case fails:

1. Abstention matches the case: the agent refuses exactly when the case is unanswerable.
2. Every `must_cite` id is cited, and no `must_not_cite` id is cited.
3. Every citation names a document in the corpus. One invented id fails the case.
4. When the case sets conflicting claims, one sentence of the answer names both, each as a whole token, and contains at least one of 12 marker substrings: conflict, contradict, however, disagree, changed, updated, differs, whereas, although, supersede, replaced, inconsistent. A hedge with no claims in it fails, and so does a marker copied from one document next to only one claim. Which documents must be cited is set by `must_cite`, as everywhere else.
5. When the case sets an expected number, at least one number in the answer lands within tolerance. Numbers are extracted with K, M, and B scaling, so "$4,200K" reads as 4,200,000.
6. When the case sets an order pair, each event is named whole in one sentence, all of its terms together, and the first event is named before the second. When it sets forbidden phrases, none appears.

Every result records the gates that applied to its case and whether each held, under eight names: abstention, required_citation, forbidden_citation, unknown_citation, contradiction, numeric, order, forbidden_phrase. The report counts failures by gate and by failure mode. A case can fail more than one gate, so the gate counts add up to more than the number of failed cases.

Grading is deterministic. Retrieval sorts by score with document id as the tiebreak, and there is no network call or model call anywhere in the package.

Document order is the one thing a run changes on purpose. The fixtures list documents in the order they were written, and the document that answers the question usually came first: the first document is a required citation in 33 of the 39 cases that require one. An agent shown that order can score by citing whatever comes first, 19 of 42. So `run_suite`, `hard-rag-evals run` and `show`, and the MCP `get_case` shuffle each case's documents with a fixed seed, `DEFAULT_SHUFFLE_SEED` = 2026, and every result records the seed. `shuffle_seed=N` or `--shuffle-seed N` picks another; `shuffle_seed=None` or `--fixture-order` keeps the fixture's order. `order_spread(agent)` reports an agent's pass count in fixture order and across 20 seeds. The grader itself looks documents up by id, so its verdict on a given answer does not depend on order; a test checks that on every gold answer under 10 permutations.

## The scores

Four scores are computed for every case and never decide a pass:

- Citation precision: the share of citations that name a real document in the corpus.
- Citation recall: the share of required documents that were cited.
- Retrieval recall: the share of gold documents the retriever pulled inside the budget.
- Faithfulness: a cited document counts as supported when it shares at least one content word with the answer text. Treat this score as weak evidence; it is a word overlap count, not a check of meaning.

There is no freshness check, no ordering check on documents, and no meaning check in the grader. When a stale or wrong document fails a case, it fails because the fixture author listed that document as forbidden, or required a different one.

## What an agent under test sees

A case has two views. The public view is an opaque id (`c-` and 12 hex characters, a hash of the descriptive id), the tier, the question, the documents in shuffled order, and the budget. It leaves out the failure mode, the descriptive id, which names the mode, the gates, and the gold ids. `hard-rag-evals list` and `show`, and the MCP tools `list_cases` and `get_case`, give the public view, sorted by public id, because the suite's own order groups cases by mode. `--dev` on any of them adds the descriptive id and the mode.

Grading has two paths. `hard-rag-evals run` and `grade` are for the person running the eval: the report names every case and every failed gate. Over MCP the default server has no per-case grading. `grade_submission` takes answers for all 42 cases and returns passed and total with an interval, overall and per tier. A submission that leaves any case out is refused. A server process grades one submission, so two cannot be subtracted to find one case's verdict. `hard-rag-evals mcp --dev` adds `grade_answer`, which returns one case's gates and notes; that is the answer key a probe at a time, and a score from a `--dev` server means nothing.

The limits: document ids belong to the published cases and some name the trap; the tier is shown; an agent that can restart the server can still compare whole submissions.

## Provenance

Every fixture, the gold answers file, and every row of the exported dataset carry one canary string with a GUID, defined in `provenance.py`. A fixture without it does not load. If a model can complete the string, the suite was in its training data. The canary was added after the cases were first published, so copies taken before it do not carry it.

Every result, report, and exported row also records `GRADER_VERSION` and `DATASET_VERSION`. The grader version is bumped by hand when a change to the grader can alter a verdict or a score. The dataset version is the sha256 of the fixture bytes the package loaded, computed at import, so a result is stamped with the data that was graded. `EXPECTED_DATASET_VERSION` in `provenance.py` is what the docs were written against; a test fails when the two differ, which means the numbers in the docs may be stale. Two results are comparable only when grader version, dataset version, and shuffle seed all match.

## Refusals

The abstention gate fails in two directions, and the report counts them apart. Over-refusal is the share of the 39 answerable cases the agent refused. Correct abstention is the share of the 3 unanswerable cases it refused. The reference agent never refuses: 0 of 39 and 0 of 3. AlwaysAbstain is 39 of 39 and 3 of 3. With only 3 unanswerable cases the second rate is weak evidence: 0 of 3 has a 95% interval of 0.00 to 0.71.

## Uncertainty

`stats.py` puts an interval on every count. Pass rates, per tier and overall, carry an exact 95% Clopper-Pearson interval. Two agents graded on the same cases are compared as a pair: the exact McNemar test on the discordant cases (those one agent passes and the other fails), and a Bonett-Price 95% interval on the difference in pass rate, which is approximate. When several agents are compared to one baseline the p-values are Holm adjusted. `compare()` raises if the two runs do not cover the same cases.

The intervals are wide because the suite is small: 0 of 5 brutal cases still allows a true rate up to 0.52. They describe sampling noise over cases like these and nothing else. The cases were written by hand, not sampled, and every agent here is deterministic, so there is no run-to-run noise to measure.

## The agents

`reference_agent/agent.py` is the baseline: IDF weighted keyword retrieval inside the budget, then the two sentences per document with the most query overlap, each prefixed with its document id, citing what it copied from. It never abstains.

`gamers.py` holds eight variants, each the reference agent plus one change, and FirstDocument, which reads nothing and cites whatever document is listed first: Hedger (cite everything retrieved, append " However, the sources may conflict."), NumberSpray (append every number found, every pairwise sum, and the total), TotalGuess (append one figure, the sum of every number found), MeanGuess (append their mean), SumMinusLargest (append their sum without the largest), CiteEverything (cite everything retrieved, text unchanged), AlwaysAbstain (the same refusal on every case), QueryEcho (open the answer with the question). `tests/test_gamers.py` pins each gamer's exact gains and losses. If a check is hardened, the matching test should fail; update it and the research summary together.

`gamers.py` also holds Fabricator, the reference agent plus one invented citation, "doc-does-not-exist-99", on every answer. `examples/demo.py` runs it. It scores 0 of 42.

## Run it

```bash
pip install -e .
python examples/demo.py             # reference and fabricating agents, by tier
python examples/grader_attacks.py   # the gamers against the checks, and the order leak
python -m pytest                    # 310 tests with the mcp extra, 86 of them gold answers passing and breaking
```

## Adding a case

Add the fixture JSON, and a builder for it in the mode's module in `failure_modes/`, following the existing builders. Write the gates the case is meant to enforce into the fixture: the required and forbidden citation lists are what make a stale or wrong document fail. Register the case in ALL_CASES through the mode's build functions, add an answer that passes it to `tests/gold_answers.json`, and add a test that pins the reference agent's result on it. The gold test fails until the new case can be passed, and fails again if one of its gates decides nothing.
