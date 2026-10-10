# Eval report: fabricating-agent

| case | mode | pass | cit_prec | cit_rec | ret_rec | faithful | notes |
| ---- | ---- | ---- | -------- | ------- | ------- | -------- | ----- |
| contradiction-01 | contradictory_sources | no | 0.67 | 1.00 | 1.00 | 0.67 | cited unknown document id: doc-does-not-exist-99; cited both sides without acknowledging the contradiction |
| stale-01 | stale_docs | no | 0.67 | 1.00 | 1.00 | 0.67 | cited a forbidden document: doc-ratelimit-2023; cited unknown document id: doc-does-not-exist-99 |
| retrieval-miss-01 | retrieval_misses | no | 0.67 | 0.00 | 0.00 | 0.67 | missing required citation: doc-fleet-maintenance; cited unknown document id: doc-does-not-exist-99 |
| fabrication-01 | citation_fabrication | no | 0.67 | 1.00 | 1.00 | 0.67 | cited unknown document id: doc-does-not-exist-99 |
| multihop-01 | multi_hop | no | 0.75 | 1.00 | 1.00 | 0.75 | cited unknown document id: doc-does-not-exist-99 |
| overflow-01 | context_overflow | no | 0.75 | 0.00 | 0.00 | 0.75 | missing required citation: doc-dbp-01; cited unknown document id: doc-does-not-exist-99 |
| unanswerable-01 | unanswerable | no | 0.00 | 1.00 | 1.00 | 0.00 | answered an unanswerable query; cited unknown document id: doc-does-not-exist-99 |

**0/7 cases passed.**
