# hard-rag-evals

Failure mode evals for agentic RAG. 42 cases across 14 failure modes,
each isolated as a gradeable behavior with a hand-built fixture and
known ground truth.

Standard RAG benchmarks measure whether the answer is right. This suite
measures how it fails: silent contradictions, stale documents outranking
current ones, vocabulary mismatch hiding the answer, fabricated
citations, dropped reasoning hops, noisy corpora, answering questions
that have no answer, events in the wrong order, quoted numbers never
summed, same-name entities conflated, injected instructions obeyed, and
needles buried in fifty documents.

## The failure modes

Twelve modes ship in easy / medium / hard tiers. The original seven
cases are the medium tier.

| mode | what breaks | easy | hard |
| ---- | ----------- | ---- | ---- |
| contradictory_sources | Corpus holds old and new versions of a fact; agent picks one silently | "replaced" is extractable | no supersession language; dates only |
| stale_docs | Long stale page outranks the short update | stale doc shares no query terms | stale doc cosmetically "updated" later |
| retrieval_misses | Query says "cars", doc says "automobiles" | partial overlap | zero overlap plus decoy distractors |
| citation_fabrication | Model invents a plausible doc id | tiny corpus | phantom id named in real doc text |
| multi_hop | Answer needs several docs plus synthesis | two docs, no reasoning | three docs plus arithmetic |
| context_overflow | More docs than budget, keyword-stuffed noise | 6 docs, mild noise | 20 docs, budget 3, exact-phrase stuffing |
| unanswerable | Corpus contains nothing relevant | obviously unrelated | near-miss corpus that tempts stitching |
| temporal_reasoning | Events with dates; "which happened first?" | two explicit dates | event dates contradict published dates |
| numeric_aggregation | Sum or average across documents | two quarters, same units | mixed $4,200K/$5.8M plus a trap doc |
| entity_disambiguation | Two people, one name | role keyword disambiguates | wrong doc stuffed with query terms |
| instruction_hierarchy | Retrieved docs try to boss the agent | blatant injection | query-level constraint vs relevance |
| long_context_needle | Answer buried in dozens of docs | 15 docs, shared terms | 50 docs, near-duplicate wrong numbers |

Two more modes go further:

| mode | tier | what breaks |
| ---- | ---- | ----------- |
| compositional | brutal (4 cases) | two or three modes at once: stale+contradiction, overflow+multihop, miss+disambiguation, temporal+stale |
| adversarial_retrieval | hard, brutal | keyword-stuffed titles, near-duplicate docs, three versions of one fact where only date reasoning picks the current truth |

## What the baseline scores

The bundled reference agent (lexical retrieval, extractive synthesis)
scores **10/42**, and the tier split is the story:

| tier | score | meaning |
| ---- | ----- | ------- |
| easy | 7/12 | passes the simple forms |
| medium | 2/12 | the original baseline behavior |
| hard | 1/13 | only the fabrication trap built for smarter agents |
| brutal | 0/5 | nothing passes |

The demo also runs a fabricating variant that appends a fake citation
id. It scores 0/42: the citation check fires on every case. That is the
check working, not the agent failing.

A careful human scores 42/42 (see `docs/human_baseline.md`): every case
is solvable by reading. The suite measures whether the agent reads as
carefully as a human would. Every failure is classified in
`docs/error_taxonomy.md`, which doubles as a debugging guide.

## Quickstart

```bash
pip install -e .
python examples/demo.py
```

No API keys. No model calls. The reference agent is deterministic, so
the demo runs anywhere.

Filter by tier or mode:

```python
from hard_rag_evals import run_suite

run_suite(agent, difficulty="hard")          # 13 cases
run_suite(agent, difficulty=("easy", "medium"))
run_suite(agent, modes="temporal_reasoning")  # one mode, all tiers
```

## Architecture

```
hard_rag_evals/
  types.py            Agent protocol, Answer, Corpus, EvalCase, EvalResult
  retrieval.py        IDF weighted keyword retrieval with a hard budget
  metrics.py          citation precision/recall, faithfulness, retrieval
                      recall, conflict acknowledgment, abstention,
                      numeric answers, event ordering, injected phrases
  runner.py           grades every case, filters by tier/mode,
                      renders the tier-grouped markdown report
  failure_modes/      one module per mode, each builds easy/medium/hard;
                      compositional.py and adversarial.py build the rest
  fixtures/           42 hand-built JSON corpora with ground truth
  reference_agent/    deterministic extractive baseline (no API keys)
docs/
  human_baseline.md   careful-pass and skim-pass human scores per tier
  error_taxonomy.md   every reference-agent failure classified (R/S/C/K/I)
examples/
  demo.py             full suite plus fabricating variant, tier bars
```

To eval your own agent, implement the `Agent` protocol and call `run_suite`:

```python
from hard_rag_evals import run_suite, render_markdown

results = run_suite(my_agent)
print(render_markdown(my_agent.name, results))
```

## Design principles

1. Isolate one failure per case. When a case fails you know exactly what broke.
2. Graduated difficulty. Easy shows the behavior; hard shows where production breaks; brutal combines modes the way the real world does.
3. Deterministic everything. Same code, same corpus, same scores, every run.
4. Strict grading. A real citation to the wrong document fails. Citing both sides of a contradiction without comment fails. Quoting numbers without summing them fails. Repeating an injected instruction fails.
5. No model in the loop. Heuristic graders keep the suite fast and free; swap in model graded checks behind the same metric names when you need them.
6. Human ceiling. Every case is solvable by careful reading; the taxonomy maps each failure to the capability it needs.

## What this does not do

It does not test generation quality, latency, or cost. It does not cover
multimodal retrieval, streaming, or conversation state. The faithfulness
and ordering metrics are lexical heuristics, not entailment models. The
human baseline is author-graded, not a third-party study.

## Roadmap

- Model graded faithfulness and conflict detection behind the metric names
- Leaderboard script for comparing agents across runs
- Multihop chains longer than two documents
- A second reference agent with embeddings, to show what hybrid retrieval buys per tier

## The one line version

42 ways RAG breaks in production, graded from "a careful intern gets
this" to "nothing passes." If your agent cannot outread the reference
implementation, it cannot outread a human either.
