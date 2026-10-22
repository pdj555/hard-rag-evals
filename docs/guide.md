# hard-rag-evals guide

The full reference: setup, usage, architecture, and design. For what this repo found and why it matters, see the [README](../README.md) and the [research summary](research.md).

## Quickstart

```bash
pip install -e .
python examples/demo.py
```

No API keys. No model calls. The reference agent is deterministic, so the demo runs anywhere.

Filter by tier or mode:

```python
from hard_rag_evals import run_suite

run_suite(agent, difficulty="hard")            # 13 cases
run_suite(agent, difficulty=("easy", "medium"))
run_suite(agent, modes="temporal_reasoning")  # one mode, all tiers
```

Eval your own agent by implementing the `Agent` protocol:

```python
from hard_rag_evals import run_suite, render_markdown

results = run_suite(my_agent)
print(render_markdown(my_agent.name, results))
```

## The failure modes

Twelve modes ship in easy / medium / hard tiers:

| mode | what breaks | easy | hard |
| ---- | ----------- | ---- | ---- |
| contradictory_sources | corpus holds old and new versions of a fact; agent picks one silently | "replaced" is extractable | no supersession language; dates only |
| stale_docs | long stale page outranks the short update | stale doc shares no query terms | stale doc cosmetically "updated" later |
| retrieval_misses | query says "cars", doc says "automobiles" | partial overlap | zero overlap plus decoy distractors |
| citation_fabrication | model invents a plausible doc id | tiny corpus | phantom id named in real doc text |
| multi_hop | answer needs several docs plus synthesis | two docs, no reasoning | three docs plus arithmetic |
| context_overflow | more docs than budget, keyword-stuffed noise | 6 docs, mild noise | 20 docs, budget 3, exact-phrase stuffing |
| unanswerable | corpus contains nothing relevant | obviously unrelated | near-miss corpus that tempts stitching |
| temporal_reasoning | events with dates; "which happened first?" | two explicit dates | event dates contradict published dates |
| numeric_aggregation | sum or average across documents | two quarters, same units | mixed $4,200K/$5.8M plus a trap doc |
| entity_disambiguation | two people, one name | role keyword disambiguates | wrong doc stuffed with query terms |
| instruction_hierarchy | retrieved docs try to boss the agent | blatant injection | query-level constraint vs relevance |
| long_context_needle | answer buried in dozens of docs | 15 docs, shared terms | 50 docs, near-duplicate wrong numbers |

Two more modes go further:

| mode | tier | what breaks |
| ---- | ---- | ----------- |
| compositional | brutal (4 cases) | two or three modes at once: stale+contradiction, overflow+multihop, miss+disambiguation, temporal+stale |
| adversarial_retrieval | hard, brutal | keyword-stuffed titles, near-duplicate docs, three versions of one fact where only date reasoning picks the current truth |

## Key features

**Isolated failure modes.** One failure per case. When a case fails you know exactly what broke.

**Graduated difficulty.** Easy shows the behavior. Hard shows where production breaks. Brutal combines modes the way the real world does.

**Strict grading.** A real citation to the wrong document fails. Citing both sides of a contradiction without comment fails. Quoting numbers without summing them fails. Repeating an injected instruction fails.

**Deterministic everything.** Same code, same corpus, same scores, every run. Heuristic graders keep the suite fast and free; swap in model-graded checks behind the same metric names when you need them.

**Solvable by reading.** Every case is built to be answerable from its corpus. The taxonomy maps each failure to the capability it needs.

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
  error_taxonomy.md   every reference-agent failure classified (R/S/C/K/I)
examples/
  demo.py             full suite plus fabricating variant, tier bars
```

## Verification

35/35 tests pass. `python -m pytest` from the repo root. The demo runs end to end with no API keys.

## What this does not do

It does not test generation quality, latency, or cost. It does not cover multimodal retrieval, streaming, or conversation state. The faithfulness and ordering metrics are lexical heuristics, not entailment models. There is no measured human baseline yet.

## Roadmap

- Model-graded faithfulness and conflict detection behind the metric names
- Leaderboard script for comparing agents across runs
- Multihop chains longer than two documents
- A second reference agent with embeddings, to show what hybrid retrieval buys per tier
