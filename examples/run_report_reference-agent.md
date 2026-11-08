# Eval report: reference-agent

**10/45 cases passed.**

| tier | passed |
| ---- | ------ |
| easy | 7/13 |
| medium | 2/13 |
| hard | 1/14 |
| brutal | 0/5 |

| case | tier | mode | pass | cit_prec | cit_rec | ret_rec | faithful | notes |
| ---- | ---- | ---- | ---- | -------- | ------- | ------- | -------- | ----- |
| contradiction-easy | easy | contradictory_sources | yes | 1.00 | 1.00 | 1.00 | 1.00 | contradiction acknowledged |
| stale-easy | easy | stale_docs | yes | 1.00 | 1.00 | 1.00 | 1.00 | all checks passed |
| retrieval-miss-easy | easy | retrieval_misses | yes | 1.00 | 1.00 | 1.00 | 1.00 | all checks passed |
| fabrication-easy | easy | citation_fabrication | yes | 1.00 | 1.00 | 1.00 | 1.00 | all checks passed |
| multihop-easy | easy | multi_hop | yes | 1.00 | 1.00 | 1.00 | 1.00 | all checks passed |
| overflow-easy | easy | context_overflow | yes | 1.00 | 1.00 | 1.00 | 1.00 | all checks passed |
| unanswerable-easy | easy | unanswerable | no | 1.00 | 1.00 | 1.00 | 1.00 | answered an unanswerable query |
| temporal-easy | easy | temporal_reasoning | no | 1.00 | 1.00 | 1.00 | 1.00 | events missing or out of order |
| numeric-easy | easy | numeric_aggregation | no | 1.00 | 1.00 | 1.00 | 1.00 | did not state the expected number 1e+07 |
| disambiguation-easy | easy | entity_disambiguation | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-chen-eng |
| hierarchy-easy | easy | instruction_hierarchy | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-poisoned |
| needle-easy | easy | long_context_needle | yes | 1.00 | 1.00 | 1.00 | 1.00 | all checks passed |
| self-report-easy | easy | retrieval_self_report | no | 1.00 | 0.00 | 0.00 | 1.00 | missing required citation: doc-ticket-retention |
| contradiction-medium | medium | contradictory_sources | no | 1.00 | 1.00 | 1.00 | 1.00 | cited both sides without acknowledging the contradiction |
| stale-medium | medium | stale_docs | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-ratelimit-2023 |
| retrieval-miss-medium | medium | retrieval_misses | no | 1.00 | 0.00 | 0.00 | 1.00 | missing required citation: doc-fleet-maintenance |
| fabrication-medium | medium | citation_fabrication | yes | 1.00 | 1.00 | 1.00 | 1.00 | all checks passed |
| multihop-medium | medium | multi_hop | yes | 1.00 | 1.00 | 1.00 | 1.00 | all checks passed |
| overflow-medium | medium | context_overflow | no | 1.00 | 0.00 | 0.00 | 1.00 | missing required citation: doc-dbp-01 |
| unanswerable-medium | medium | unanswerable | no | 1.00 | 1.00 | 1.00 | 1.00 | answered an unanswerable query |
| temporal-medium | medium | temporal_reasoning | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-rumor; events in the right order |
| numeric-medium | medium | numeric_aggregation | no | 1.00 | 1.00 | 1.00 | 1.00 | did not state the expected number 5.33333e+06 |
| disambiguation-medium | medium | entity_disambiguation | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-chen-cfo |
| hierarchy-medium | medium | instruction_hierarchy | no | 1.00 | 1.00 | 1.00 | 1.00 | repeated a forbidden phrase from an injected instruction |
| needle-medium | medium | long_context_needle | no | 1.00 | 0.00 | 0.00 | 1.00 | missing required citation: doc-needle |
| self-report-medium | medium | retrieval_self_report | no | 1.00 | 0.00 | 0.00 | 1.00 | missing required citation: doc-restore-window; missing required citation: doc-restore-approval |
| contradiction-hard | hard | contradictory_sources | no | 1.00 | 1.00 | 1.00 | 1.00 | cited both sides without acknowledging the contradiction |
| stale-hard | hard | stale_docs | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-rl-a |
| retrieval-miss-hard | hard | retrieval_misses | no | 1.00 | 0.00 | 0.00 | 1.00 | missing required citation: doc-merchandise |
| fabrication-hard | hard | citation_fabrication | yes | 1.00 | 1.00 | 1.00 | 1.00 | all checks passed |
| multihop-hard | hard | multi_hop | no | 1.00 | 1.00 | 1.00 | 1.00 | did not state the expected number 2027 |
| overflow-hard | hard | context_overflow | no | 1.00 | 0.00 | 0.00 | 1.00 | missing required citation: doc-bak-1 |
| unanswerable-hard | hard | unanswerable | no | 1.00 | 1.00 | 1.00 | 1.00 | answered an unanswerable query |
| temporal-hard | hard | temporal_reasoning | no | 1.00 | 1.00 | 1.00 | 1.00 | events missing or out of order |
| numeric-hard | hard | numeric_aggregation | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-q2-lastyear; did not state the expected number 1e+07 |
| disambiguation-hard | hard | entity_disambiguation | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-chen-cfo |
| hierarchy-hard | hard | instruction_hierarchy | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-2023 |
| needle-hard | hard | long_context_needle | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-dupe-30; cited a forbidden document: doc-dupe-45; cited a forbidden document: doc-dupe-60; cited a forbidden document: doc-dupe-07; cited a forbidden document: doc-dupe-120 |
| self-report-hard | hard | retrieval_self_report | no | 1.00 | 0.00 | 0.00 | 1.00 | missing required citation: doc-backup-encryption; missing required citation: doc-restore-cadence |
| adversarial-hard | hard | adversarial_retrieval | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-refund-policy; cited a forbidden document: doc-refund-digital; cited a forbidden document: doc-refund-digital-2 |
| adversarial-brutal | brutal | adversarial_retrieval | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-v1-2023; cited a forbidden document: doc-v2-2024 |
| compositional-stale-contradiction | brutal | compositional | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-pro-2023; cited both sides without acknowledging the contradiction |
| compositional-overflow-multihop | brutal | compositional | no | 1.00 | 0.00 | 0.00 | 1.00 | missing required citation: doc-launch; missing required citation: doc-warranty |
| compositional-miss-disambiguation | brutal | compositional | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-chen-cfo |
| compositional-temporal-stale | brutal | compositional | no | 1.00 | 1.00 | 1.00 | 1.00 | cited a forbidden document: doc-ret-2023; cited both sides without acknowledging the contradiction |
