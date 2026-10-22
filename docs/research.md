# Research summary

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.svg">
  <img alt="42 cases by tier. The reference agent passes 7 of 12 easy, 2 of 12 medium, 1 of 13 hard, 0 of 5 brutal. Cheap tricks turn 3 failed cases into passes, including the sentence: However, the sources may conflict." src="assets/hero-light.svg" width="100%">
</picture>

When an agent answers from documents, nobody goes back and reads the sources. So the answer has to carry its own evidence. This suite checks whether it does.

It's the same question as [agent-harness](https://github.com/pdj555/agent-harness), applied to answers instead of diffs: **how can we trust what an agent hands back without a human checking it?**

## What I built

42 cases, each built around one way RAG breaks: a stale doc that outranks the update, two sources that disagree, a citation to a doc that doesn't exist, a question the corpus can't answer, an instruction planted inside a retrieved doc. 12 failure modes come in easy, medium, and hard. Two more go further: compositional cases stack two or three failures, and adversarial cases use keyword-stuffed decoys. One failure per case, so a fail tells you what broke.

## Results

| Agent | Easy | Medium | Hard | Brutal | Total |
| --- | --- | --- | --- | --- | --- |
| Reference (lexical retrieval, extractive answers) | 7/12 | 2/12 | 1/13 | 0/5 | 10/42 |
| Reference plus one invented citation | 0/12 | 0/12 | 0/13 | 0/5 | 0/42 |

One fake citation zeroes every case. That check is strict on purpose.

## The grader can be gamed too

Any cheap check an agent can see, it can satisfy without doing the work. So I wrote four gaming agents. Each is the reference agent plus one trick aimed at one check, and none of them reads more carefully.

| Gaming agent | Trick | Score | Gamed into a pass |
| --- | --- | --- | --- |
| Hedger | cite every retrieved doc, add "However, the sources may conflict." | 11/42 | both contradiction cases, medium and hard |
| Number spray | append every number, pairwise sum, and total from the retrieved docs | 11/42 | numeric-easy |
| Cite everything | cite every retrieved doc | 9/42 | none |
| Always abstain | refuse every question | 3/42 | the 3 unanswerable cases, at the cost of 10 others |

The reference agent scores 10/42. Two checks fall:

- **Contradiction.** It passes an answer that cites both sides and uses a word like "however." The hedger never detects a contradiction.
- **Numeric.** It passes if any number in the answer matches. The spray hits the right total on 2 of the 4 numeric cases. One passes outright; the other is still failed by the forbidden-citation check.

Two hold. Citing everything gains nothing, because citing a forbidden doc fails the case. Refusing everything loses far more than it gains.

```bash
python examples/grader_attacks.py
```

That's the same lesson as the test suites in agent-harness, one level up: keyword graders here, unit tests there.

## Where it breaks

- The faithfulness, ordering, and contradiction checks are word matching, not understanding. The hedger shows the cost.
- The numeric check passes if any number in the answer is right. The spray shows the cost.
- The reference agent is deliberately naive. I haven't run a real model through the suite yet.
- 42 hand-built cases. No measured human baseline.

## Next

1. Harden the two checks that fell: make the contradiction check require naming which claim is current, and make the numeric check reject answers that list more than one candidate.
2. Run real models and report scores by tier.
3. Add a gaming agent for every remaining check, and rerun all of them after each hardening.

Every case and failure code: [error_taxonomy.md](error_taxonomy.md).

Preston Jones · p@pdj.dev
