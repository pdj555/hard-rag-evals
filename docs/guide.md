# Guide

What this repo found is in the [README](../README.md). The experiment, in full, is in the [research summary](research.md). This guide covers how a case is built, how grading runs, and what the scores do and do not decide.

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

Grading is deterministic. Retrieval sorts by score with document id as the tiebreak, and there is no randomness, network call, or model call anywhere in the package.

## The scores

Four scores are computed for every case and never decide a pass:

- Citation precision: the share of citations that name a real document in the corpus.
- Citation recall: the share of required documents that were cited.
- Retrieval recall: the share of gold documents the retriever pulled inside the budget.
- Faithfulness: a cited document counts as supported when it shares at least one content word with the answer text. Treat this score as weak evidence; it is a word overlap count, not a check of meaning.

There is no freshness check, no ordering check on documents, and no meaning check in the grader. When a stale or wrong document fails a case, it fails because the fixture author listed that document as forbidden, or required a different one.

## The agents

`reference_agent/agent.py` is the baseline: IDF weighted keyword retrieval inside the budget, then the two sentences per document with the most query overlap, each prefixed with its document id, citing what it copied from. It never abstains.

`gamers.py` holds five variants, each the reference agent plus one change: Hedger (cite everything retrieved, append " However, the sources may conflict."), NumberSpray (append every number found, every pairwise sum, and the total), CiteEverything (cite everything retrieved, text unchanged), AlwaysAbstain (the same refusal on every case), QueryEcho (open the answer with the question). `tests/test_gamers.py` pins each gamer's exact gains and losses. If a check is hardened, the matching test should fail; update it and the research summary together.

`examples/demo.py` also runs a fabricating variant: the reference agent plus one invented citation, "doc-does-not-exist-99", on every answer. It scores 0 of 42.

## Run it

```bash
pip install -e .
python examples/demo.py             # reference and fabricating agents, by tier
python examples/grader_attacks.py   # the five gamers against the checks
python -m pytest                    # 125 tests, 86 of them gold answers passing and breaking
```

## Adding a case

Add the fixture JSON, and a builder for it in the mode's module in `failure_modes/`, following the existing builders. Write the gates the case is meant to enforce into the fixture: the required and forbidden citation lists are what make a stale or wrong document fail. Register the case in ALL_CASES through the mode's build functions, add an answer that passes it to `tests/gold_answers.json`, and add a test that pins the reference agent's result on it. The gold test fails until the new case can be passed, and fails again if one of its gates decides nothing.
