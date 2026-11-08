# Guide

What this repo found is in the [README](../README.md). The experiment, in full, is in the [research summary](research.md). This guide covers how a case is built, how grading runs, and what the scores do and do not decide.

## A case

Each case is one JSON fixture in `hard_rag_evals/fixtures/`, built by a module in `hard_rag_evals/failure_modes/`. The registry in `failure_modes/__init__.py` assembles all 45 cases as ALL_CASES: 13 modes at easy, medium, and hard, plus adversarial retrieval (2 cases) and compositional (4).

A fixture holds:

- A query and a corpus of short documents, each with an id, a source, and a published date.
- A retrieval budget: how many documents, and how many characters, the agent may pull.
- The gates for the case: required citations (`must_cite`), forbidden citations (`must_not_cite`), a conflict pair, an expected number with a tolerance, an order pair, forbidden phrases, and an abstain flag for unanswerable cases.
- An "expected" answer in prose, and the gold document ids. The grader never reads the prose; the gold ids feed only the retrieval recall score.

## How grading runs

`runner.grade()` is all or nothing. Fail any gate and the case fails:

1. The retrieval report checks out against the corpus and the case budget. Every reported retrieved id names a real document, appears once, and fits inside the budget in the order reported (at most `max_docs` documents, at most `max_chars` of text, with a first document allowed past the character cap on its own, as the retriever itself allows). Ids that fail this check are dropped, retrieval recall is computed from what remains, and any dropped id fails the case. Every citation must also name a document in the set that remains: citing a document the report cannot account for fails the case.
2. Abstention matches the case: the agent refuses exactly when the case is unanswerable.
3. Every `must_cite` id is cited, and no `must_not_cite` id is cited.
4. Every citation names a document in the corpus. One invented id fails the case.
5. When the case sets a conflict pair, both documents are cited and the answer contains at least one of 13 marker substrings: conflict, contradict, however, disagree, changed, updated, differs, whereas, although, supersede, replaced, inconsistent. It is a substring search on the lowercased text. Nothing compares the two claims.
6. When the case sets an expected number, at least one number in the answer lands within tolerance. Numbers are extracted with K, M, and B scaling, so "$4,200K" reads as 4,200,000.
7. When the case sets an order pair, the events appear in that order. When it sets forbidden phrases, none appears.

Grading is deterministic. Retrieval sorts by score with document id as the tiebreak, and there is no randomness, network call, or model call anywhere in the package.

## The scores

Four scores are computed for every case and never decide a pass:

- Citation precision: the share of citations that name a real document in the corpus.
- Citation recall: the share of required documents that were cited.
- Retrieval recall: the share of gold documents in the checked retrieved set: reported ids that name real documents and fit inside the budget.
- Faithfulness: a cited document counts as supported when it shares at least one content word with the answer text. Treat this score as weak evidence; it is a word overlap count, not a check of meaning.

There is no freshness check, no ordering check on documents, and no meaning check in the grader. When a stale or wrong document fails a case, it fails because the fixture author listed that document as forbidden, or required a different one.

## The agents

`reference_agent/agent.py` is the baseline: IDF weighted keyword retrieval inside the budget, then the two sentences per document with the most query overlap, each prefixed with its document id, citing what it copied from. It never abstains.

`gamers.py` holds six variants, each the reference agent plus one change: Hedger (cite everything retrieved, append " However, the sources may conflict."), NumberSpray (append every number found, every pairwise sum, and the total), CiteEverything (cite everything retrieved, text unchanged), AlwaysAbstain (the same refusal on every case), RetrievalFabricator (report every document in the corpus as retrieved), and CorpusSmuggler (read the whole corpus with no budget, cite from all of it, and report only the budgeted retrieval). `tests/test_gamers.py` pins the first four gamers' exact gains and losses, and `tests/test_verification.py` pins the two report gamers. If a check is hardened, the matching test should fail; update it and the research summary together.

`examples/demo.py` also runs a fabricating variant: the reference agent plus one invented citation, "doc-does-not-exist-99", on every answer. It scores 0 of 45.

## Run it

```bash
pip install -e .
python examples/demo.py             # reference and fabricating agents, by tier
python examples/grader_attacks.py   # the six gamers against the checks
python -m pytest                    # 51 tests: depth 18, metrics 8, runner 5, gamers 4, verification 16
```

## Adding a case

Add the fixture JSON, and a builder for it in the mode's module in `failure_modes/`, following the existing builders. Write the gates the case is meant to enforce into the fixture: the required and forbidden citation lists are what make a stale or wrong document fail. Register the case in ALL_CASES through the mode's build functions, and add a test that pins the reference agent's result on it.
