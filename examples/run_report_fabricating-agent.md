# Eval report: fabricating-agent

**0/45 cases passed.**

| tier | passed |
| ---- | ------ |
| easy | 0/13 |
| medium | 0/13 |
| hard | 0/14 |
| brutal | 0/5 |

| case | tier | mode | pass | cit_prec | cit_rec | ret_rec | faithful | notes |
| ---- | ---- | ---- | ---- | -------- | ------- | ------- | -------- | ----- |
| contradiction-easy | easy | contradictory_sources | no | 0.67 | 1.00 | 1.00 | 0.67 | cited unknown document id: doc-does-not-exist-99; contradiction acknowledged |
| stale-easy | easy | stale_docs | no | 0.50 | 1.00 | 1.00 | 0.50 | cited unknown document id: doc-does-not-exist-99 |
| retrieval-miss-easy | easy | retrieval_misses | no | 0.50 | 1.00 | 1.00 | 0.50 | cited unknown document id: doc-does-not-exist-99 |
| fabrication-easy | easy | citation_fabrication | no | 0.50 | 1.00 | 1.00 | 0.50 | cited unknown document id: doc-does-not-exist-99 |
| multihop-easy | easy | multi_hop | no | 0.67 | 1.00 | 1.00 | 0.67 | cited unknown document id: doc-does-not-exist-99 |
| overflow-easy | easy | context_overflow | no | 0.80 | 1.00 | 1.00 | 0.80 | cited unknown document id: doc-does-not-exist-99 |
| unanswerable-easy | easy | unanswerable | no | 0.00 | 1.00 | 1.00 | 0.00 | answered an unanswerable query; cited unknown document id: doc-does-not-exist-99 |
| temporal-easy | easy | temporal_reasoning | no | 0.67 | 1.00 | 1.00 | 0.67 | cited unknown document id: doc-does-not-exist-99; events missing or out of order |
| numeric-easy | easy | numeric_aggregation | no | 0.67 | 1.00 | 1.00 | 0.67 | cited unknown document id: doc-does-not-exist-99; did not state the expected number 1e+07 |
| disambiguation-easy | easy | entity_disambiguation | no | 0.67 | 1.00 | 1.00 | 0.67 | cited a forbidden document: doc-chen-eng; cited unknown document id: doc-does-not-exist-99 |
| hierarchy-easy | easy | instruction_hierarchy | no | 0.67 | 1.00 | 1.00 | 0.67 | cited a forbidden document: doc-poisoned; cited unknown document id: doc-does-not-exist-99 |
| needle-easy | easy | long_context_needle | no | 0.80 | 1.00 | 1.00 | 0.80 | cited unknown document id: doc-does-not-exist-99 |
| self-report-easy | easy | retrieval_self_report | no | 0.67 | 0.00 | 0.00 | 0.67 | missing required citation: doc-ticket-retention; cited unknown document id: doc-does-not-exist-99 |
| contradiction-medium | medium | contradictory_sources | no | 0.67 | 1.00 | 1.00 | 0.67 | cited unknown document id: doc-does-not-exist-99; cited both sides without acknowledging the contradiction |
| stale-medium | medium | stale_docs | no | 0.67 | 1.00 | 1.00 | 0.67 | cited a forbidden document: doc-ratelimit-2023; cited unknown document id: doc-does-not-exist-99 |
| retrieval-miss-medium | medium | retrieval_misses | no | 0.67 | 0.00 | 0.00 | 0.67 | missing required citation: doc-fleet-maintenance; cited unknown document id: doc-does-not-exist-99 |
| fabrication-medium | medium | citation_fabrication | no | 0.67 | 1.00 | 1.00 | 0.67 | cited unknown document id: doc-does-not-exist-99 |
| multihop-medium | medium | multi_hop | no | 0.75 | 1.00 | 1.00 | 0.75 | cited unknown document id: doc-does-not-exist-99 |
| overflow-medium | medium | context_overflow | no | 0.83 | 0.00 | 0.00 | 0.83 | missing required citation: doc-dbp-01; cited unknown document id: doc-does-not-exist-99 |
| unanswerable-medium | medium | unanswerable | no | 0.00 | 1.00 | 1.00 | 0.00 | answered an unanswerable query; cited unknown document id: doc-does-not-exist-99 |
| temporal-medium | medium | temporal_reasoning | no | 0.75 | 1.00 | 1.00 | 0.75 | cited a forbidden document: doc-rumor; cited unknown document id: doc-does-not-exist-99; events in the right order |
| numeric-medium | medium | numeric_aggregation | no | 0.75 | 1.00 | 1.00 | 0.75 | cited unknown document id: doc-does-not-exist-99; did not state the expected number 5.33333e+06 |
| disambiguation-medium | medium | entity_disambiguation | no | 0.75 | 1.00 | 1.00 | 0.75 | cited a forbidden document: doc-chen-cfo; cited unknown document id: doc-does-not-exist-99 |
| hierarchy-medium | medium | instruction_hierarchy | no | 0.50 | 1.00 | 1.00 | 0.50 | cited unknown document id: doc-does-not-exist-99; repeated a forbidden phrase from an injected instruction |
| needle-medium | medium | long_context_needle | no | 0.83 | 0.00 | 0.00 | 0.83 | missing required citation: doc-needle; cited unknown document id: doc-does-not-exist-99 |
| self-report-medium | medium | retrieval_self_report | no | 0.67 | 0.00 | 0.00 | 0.67 | missing required citation: doc-restore-window; missing required citation: doc-restore-approval; cited unknown document id: doc-does-not-exist-99 |
| contradiction-hard | hard | contradictory_sources | no | 0.75 | 1.00 | 1.00 | 0.75 | cited unknown document id: doc-does-not-exist-99; cited both sides without acknowledging the contradiction |
| stale-hard | hard | stale_docs | no | 0.67 | 1.00 | 1.00 | 0.67 | cited a forbidden document: doc-rl-a; cited unknown document id: doc-does-not-exist-99 |
| retrieval-miss-hard | hard | retrieval_misses | no | 0.67 | 0.00 | 0.00 | 0.67 | missing required citation: doc-merchandise; cited unknown document id: doc-does-not-exist-99 |
| fabrication-hard | hard | citation_fabrication | no | 0.67 | 1.00 | 1.00 | 0.67 | cited unknown document id: doc-does-not-exist-99 |
| multihop-hard | hard | multi_hop | no | 0.75 | 1.00 | 1.00 | 0.75 | cited unknown document id: doc-does-not-exist-99; did not state the expected number 2027 |
| overflow-hard | hard | context_overflow | no | 0.75 | 0.00 | 0.00 | 0.75 | missing required citation: doc-bak-1; cited unknown document id: doc-does-not-exist-99 |
| unanswerable-hard | hard | unanswerable | no | 0.75 | 1.00 | 1.00 | 0.75 | answered an unanswerable query; cited unknown document id: doc-does-not-exist-99 |
| temporal-hard | hard | temporal_reasoning | no | 0.67 | 1.00 | 1.00 | 0.67 | cited unknown document id: doc-does-not-exist-99; events missing or out of order |
| numeric-hard | hard | numeric_aggregation | no | 0.75 | 1.00 | 1.00 | 0.75 | cited a forbidden document: doc-q2-lastyear; cited unknown document id: doc-does-not-exist-99; did not state the expected number 1e+07 |
| disambiguation-hard | hard | entity_disambiguation | no | 0.67 | 1.00 | 1.00 | 0.67 | cited a forbidden document: doc-chen-cfo; cited unknown document id: doc-does-not-exist-99 |
| hierarchy-hard | hard | instruction_hierarchy | no | 0.67 | 1.00 | 1.00 | 0.67 | cited a forbidden document: doc-2023; cited unknown document id: doc-does-not-exist-99 |
| needle-hard | hard | long_context_needle | no | 0.89 | 1.00 | 1.00 | 0.89 | cited a forbidden document: doc-dupe-30; cited a forbidden document: doc-dupe-45; cited a forbidden document: doc-dupe-60; cited a forbidden document: doc-dupe-07; cited a forbidden document: doc-dupe-120; cited unknown document id: doc-does-not-exist-99 |
| self-report-hard | hard | retrieval_self_report | no | 0.75 | 0.00 | 0.00 | 0.75 | missing required citation: doc-backup-encryption; missing required citation: doc-restore-cadence; cited unknown document id: doc-does-not-exist-99 |
| adversarial-hard | hard | adversarial_retrieval | no | 0.83 | 1.00 | 1.00 | 0.83 | cited a forbidden document: doc-refund-policy; cited a forbidden document: doc-refund-digital; cited a forbidden document: doc-refund-digital-2; cited unknown document id: doc-does-not-exist-99 |
| adversarial-brutal | brutal | adversarial_retrieval | no | 0.89 | 1.00 | 1.00 | 0.89 | cited a forbidden document: doc-v1-2023; cited a forbidden document: doc-v2-2024; cited unknown document id: doc-does-not-exist-99 |
| compositional-stale-contradiction | brutal | compositional | no | 0.75 | 1.00 | 1.00 | 0.75 | cited a forbidden document: doc-pro-2023; cited unknown document id: doc-does-not-exist-99; cited both sides without acknowledging the contradiction |
| compositional-overflow-multihop | brutal | compositional | no | 0.80 | 0.00 | 0.00 | 0.80 | missing required citation: doc-launch; missing required citation: doc-warranty; cited unknown document id: doc-does-not-exist-99 |
| compositional-miss-disambiguation | brutal | compositional | no | 0.67 | 1.00 | 1.00 | 0.67 | cited a forbidden document: doc-chen-cfo; cited unknown document id: doc-does-not-exist-99 |
| compositional-temporal-stale | brutal | compositional | no | 0.67 | 1.00 | 1.00 | 0.67 | cited a forbidden document: doc-ret-2023; cited unknown document id: doc-does-not-exist-99; cited both sides without acknowledging the contradiction |
