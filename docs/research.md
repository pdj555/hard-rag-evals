# Research summary

An agent that answers from retrieved documents can fail in ways its answer hides: a citation to a document that does not exist, the stale version quoted, a contradiction buried, an answer where the documents hold nothing. This repo builds one case per failure, grades with hard gates, then attacks the grader itself.

## What was built

14 failure modes, 42 cases. 12 modes come in three tiers, easy, medium, and hard: contradictory sources, stale documents, retrieval misses, citation fabrication, multi hop questions, context overflow, unanswerable questions, temporal reasoning, numeric aggregation, entity disambiguation, instruction hierarchy, and a needle in a long context. Two more modes go further: adversarial retrieval (2 cases) and compositional cases (4) that stack two or three failures in one case. Tier counts: easy 12, medium 12, hard 13, brutal 5. Each case is one JSON fixture: a query, a small corpus of dated documents, a retrieval budget, and the gates for that case written into the fixture.

Gate coverage across the suite: a required citation list on 39 of 42 cases, a forbidden citation list on 16, a pair of conflicting claims on 5, an expected number on 4, an abstention requirement on 3, an order check on 3, forbidden phrases on 2.

## Every case can be passed

Each case has one hand-written answer in `tests/gold_answers.json`, and all 42 pass. Each gold answer is then broken one way at a time: a required citation dropped, a forbidden or invented citation added, the refusal flipped, a hedge put in place of the comparison, the inputs quoted in place of the computed number, the injected phrase repeated. Every break fails its case, so no gate on any case is decoration.

Writing them found a case no answer could pass. compositional-temporal-stale forbade citing the stale 2023 retention document, and its conflict gate required citing that same document. The conflict gate now checks the two claims stated in the answer, 30 and 90 days, and leaves citations to the citation lists, so the case asks for what its prose always said: cite the current document and say the period changed.

## The experiment

The reference agent is a baseline, not a model. It ranks documents by IDF weighted keyword overlap, keeps the top documents inside the budget (5 documents, 8,000 characters by default), copies the two sentences from each with the most query overlap, and cites the documents it copied from. It never abstains.

| Agent | Easy | Medium | Hard | Brutal | Total |
| --- | --- | --- | --- | --- | --- |
| Gold answers | 12/12 | 12/12 | 13/13 | 5/5 | 42/42 |
| Reference | 6/12 | 2/12 | 1/13 | 0/5 | 9/42 |
| Reference plus one invented citation on every answer | 0/12 | 0/12 | 0/13 | 0/5 | 0/42 |

The one hard case the reference agent passes is citation fabrication at hard tier, and it passes all three fabrication tiers for one reason: it only ever cites documents it retrieved. It used to pass contradiction-easy as well, on a sentence copied out of the newer document, "This change replaced the previous 30 day window." That sentence has a marker word and one of the two claims. The check now wants both claims in the sentence, so the pass is gone, and the reference agent went from 10 to 9.

## The grader can be gamed too

Five agents each add one trick to the reference agent. Their results are pinned by tests, so hardening a check breaks the matching test and is recorded here.

Still beaten:

- The numeric check. NumberSpray appends every number in the retrieved documents, every pairwise sum, and the grand total. The gate needs one number in the text within tolerance of the expected value. The spray hits the expected value on 2 of the 4 numeric cases: one passes outright, numeric-easy, and the other still fails on a forbidden citation in the underlying answer. It cannot hit numeric-medium at all, which expects an average no sum produces. Score: 10 of 42.

Beaten before, held now:

- The contradiction check. The Hedger cites every retrieved document and appends "However, the sources may conflict." It used to turn contradiction-medium and contradiction-hard into passes, because the check asked for both documents cited and one marker word anywhere. The check now asks for one sentence holding both claims and a marker. The hedge holds neither claim. The Hedger gains nothing and scores 8 of 42.
- The order check. QueryEcho opens the answer with the question, "Which launched first, the Aurora X1 or the Vega S2?", which names Aurora before Vega without dating either. The check used to compare where the terms of each event first appear anywhere in the answer, and the echo won temporal-easy and temporal-hard. The check now counts an event only where one sentence names all of its terms. QueryEcho gains nothing and scores 9 of 42, the reference score.

Held, against these tricks:

- The unknown citation gate. One invented citation fails the case, on all 42 at once for the fabricating variant.
- The forbidden citation gate. CiteEverything gains nothing and finishes below the reference agent, 8 of 42 against 9. This gate is also what stops the spray from converting a second numeric case.
- The abstention gate. AlwaysAbstain wins exactly the 3 unanswerable cases and loses the other 39.

The forbidden phrase gate is the one gate with no gaming agent aimed at it.

## Where it breaks

- No model has been run through the suite. The repo has no model, API, or network code and zero runtime dependencies. Every score is a score of one scripted baseline and its variants.
- The corpora are hand built by the suite's author, 2 to 50 short documents per case, with the gates written into the same fixtures. The gold answers are by the same author. No human baseline has been measured.
- The contradiction check reads tokens, not meaning. "Changed from 14 to 30 days" names both claims and a marker and passes, though it gets the direction backwards. A genuine comparison that uses none of the 12 marker words fails.
- The numeric tolerance is wide: 500,000 on an expected 10,000,000 is a 5 percent band, and nothing asks the answer to commit to one figure.
- The four scores (citation precision and recall, retrieval recall, faithfulness) never decide a pass, and faithfulness counts a citation as supported when it shares one content word with the answer. Each fixture also carries an "expected" answer in prose that the grader loads and never reads.

## Next

1. Run a real model through the suite and compare its failure profile with the baseline's.
2. Make the numeric check ask for one committed figure, and record the spray's pinned test breaking.
3. Write a gaming agent for the forbidden phrase gate, so every gate has an attack on record.

Preston Jones · p@pdj.dev
