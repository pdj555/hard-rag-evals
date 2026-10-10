# Eval report: reference-agent

| case | mode | pass | cit_prec | cit_rec | ret_rec | faithful | notes |
| ---- | ---- | ---- | -------- | ------- | ------- | -------- | ----- |
| contradiction-01 | contradictory_sources | no | 1.00 | 1.00 | 1.00 | 1.00 | cited both sides without acknowledging the contradiction |
| stale-01 | stale_docs | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-ratelimit-2023 |
| retrieval-miss-01 | retrieval_misses | no | 1.00 | 0.00 | 0.00 | 1.00 | missing required citation: doc-fleet-maintenance |
| fabrication-01 | citation_fabrication | yes | 1.00 | 1.00 | 1.00 | 1.00 | all checks passed |
| multihop-01 | multi_hop | yes | 1.00 | 1.00 | 1.00 | 1.00 | all checks passed |
| overflow-01 | context_overflow | no | 1.00 | 0.00 | 0.00 | 1.00 | missing required citation: doc-dbp-01 |
| unanswerable-01 | unanswerable | no | 1.00 | 1.00 | 1.00 | 1.00 | answered an unanswerable query |

**2/7 cases passed.**
