# Research summary

An agent that answers from retrieved documents can fail in ways its answer hides: a citation to a document that does not exist, the stale version quoted, a contradiction buried, an answer where the documents hold nothing. This repo builds one case per failure, grades with hard gates, then attacks the grader itself.

## What was built

14 failure modes, 42 cases. 12 modes come in three tiers, easy, medium, and hard: contradictory sources, stale documents, retrieval misses, citation fabrication, multi hop questions, context overflow, unanswerable questions, temporal reasoning, numeric aggregation, entity disambiguation, instruction hierarchy, and a needle in a long context. Two more modes go further: adversarial retrieval (2 cases) and compositional cases (4) that stack two or three failures in one case. Tier counts: easy 12, medium 12, hard 13, brutal 5. Each case is one JSON fixture: a query, a small corpus of dated documents, a retrieval budget, and the gates for that case written into the fixture.

Gate coverage across the suite: a required citation list on 39 of 42 cases, a forbidden citation list on 16, a conflict pair on 5, an expected number on 4, an abstention requirement on 3, an order check on 3, forbidden phrases on 2.

## The experiment

The reference agent is a baseline, not a model. It ranks documents by IDF weighted keyword overlap, keeps the top documents inside the budget (5 documents, 8,000 characters by default), copies the two sentences from each with the most query overlap, and cites the documents it copied from. It never abstains.

| Agent | Easy | Medium | Hard | Brutal | Total |
| --- | --- | --- | --- | --- | --- |
| Reference | 7/12 | 2/12 | 1/13 | 0/5 | 10/42 |
| Reference plus one invented citation on every answer | 0/12 | 0/12 | 0/13 | 0/5 | 0/42 |

The one hard case the reference agent passes is citation fabrication at hard tier, and it passes all three fabrication tiers for one reason: it only ever cites documents it retrieved. Its one contradiction pass, at easy tier, rides on a sentence copied out of the newer document, "This change replaced the previous 30 day window." The word "replaced" is one of the grader's 13 marker words. The agent detected nothing.

## The grader can be gamed too

Four agents each add one trick to the reference agent. Their results are pinned by tests, so hardening a check is expected to break the matching test and be recorded here.

Beaten:

- The contradiction check. The Hedger cites every retrieved document and appends one sentence: "However, the sources may conflict." Both contradiction cases the reference agent fails turn into passes, and the check is also satisfied on the two compositional conflict cases, which still fail on a forbidden citation the trick adds. The check asks for both documents and one marker word. It never compares the two claims.
- The numeric check. NumberSpray appends every number in the retrieved documents, every pairwise sum, and the grand total. The gate needs one number in the text within tolerance of the expected value. The spray hits the expected value on 2 of the 4 numeric cases: one passes outright, the other still fails on a forbidden citation in the underlying answer. It cannot hit numeric-medium at all, which expects an average no sum produces.

Held, against these tricks:

- The unknown citation gate. One invented citation fails the case, on all 42 at once for the fabricating variant.
- The forbidden citation gate. CiteEverything gains nothing and finishes below the reference agent, 9 of 42 against 10. This gate is also what stops the Hedger and the spray from converting two more cases.
- The abstention gate. AlwaysAbstain wins exactly the 3 unanswerable cases and loses the other 39.

Two gates have no gaming agent aimed at them yet: the order check and the forbidden phrase check. Which checks can be gamed is answered for five of the seven gates.

## Where it breaks

- No model has been run through the suite. The repo has no model, API, or network code and zero runtime dependencies. Every score is a score of one scripted baseline and its variants.
- The corpora are hand built by the suite's author, 2 to 50 short documents per case, with the gates written into the same fixtures. No human baseline has been measured.
- The contradiction check cannot tell detecting a conflict from copying the word "replaced" out of a document, and it fails a genuine acknowledgment that uses none of its 13 words.
- The numeric tolerance is wide: 500,000 on an expected 10,000,000 is a 5 percent band.
- The four scores (citation precision and recall, retrieval recall, faithfulness) never decide a pass, and faithfulness counts a citation as supported when it shares one content word with the answer. Each fixture also carries an "expected" answer in prose that the grader loads and never reads.

## Next

1. Run a real model through the suite and compare its failure profile with the baseline's.
2. Harden the contradiction check so it compares the two claims, and record which pinned gamer tests break.
3. Write gaming agents for the order and forbidden phrase gates, so all seven gates have an attack on record.

Preston Jones · p@pdj.dev
