# Formal resource diagnosis v1

This maintenance candidate adds an explicit, read-only engineering diagnostic command. It does not change the formal evaluator or raise any resource bound. The installed failure is a real capacity rejection: canonical validation work from the current context, the old-method context and completed public-ancestor replays is combined before returning a batch.

The diagnostic copies the actual immutable Store bundles and four SHA-verified registered input files into a temporary project. It reconstructs the existing frozen engineering snapshot, delegates to the unchanged approved evaluator and observes counters without suppressing exceptions, clearing caches, skipping ancestors or committing results. Instrumentation is restored on success and failure. It reports current, old and public-replay bytes, union review-node counts, the failing call site, each historical replay context and direct-child accounting. No row-level inputs or private computation values enter its public receipt.

The byte bound is 128,000,000 canonical validation-work bytes, review-node bound 128, predecessor depth 64, semantic-ancestor bound 4096 and validation deadline 180 seconds. These are existing guards, not physical-memory measurements. Multiple as-of snapshots and plans may validate the same raw source, but treating those separate operations as free would change the existing work-budget policy. The diagnostic therefore does not deduct repeated source content or use a higher cap.

The final resource gate intentionally prevents a partially prepared batch from becoming a submit-ready object after the context has exceeded its limit. Per-plan technical-failure handling does not override this global gate. The current failure remains incomplete: no new formal reviews, no new economic result and no automatic historical backfill. The diagnostic's return values are temporary engineering observations only.

Run explicitly from this source checkout:

```
python3 scripts/diagnose_formal_resources.py --project-root PROJECT_ROOT
```

`PROJECT_ROOT` must be the authorized project with its actual September 30 frozen batch and registered input manifest. The command writes only disposable temporary copies and JSON to stdout. Save the output as an engineering receipt, never as a native daily-review result. It does not prepare an outbox, call Store commit, install code, access the network, publish or upload.

The maintenance deliverable improves reproducible diagnosis only. It does **not** solve the cumulative-history capacity bottleneck. Any future bounded shared-cache or different accounting design needs a separate reviewed evaluator version, complete old-method identity compatibility, and independent attack/resource tests. No such migration or financial-rule change is included here. The old 16-source and formal 19-source identities remain unchanged.

## Observed capacity accounting

| Frozen historical batch | Own current + old work bytes | Child replay work bytes | Combined work bytes |
| --- | ---: | ---: | ---: |
| September 27 | 8,935,980 | 0 | 8,935,980 |
| September 28 | 38,211,100 | 8,935,980 | 47,147,080 |
| September 29 | 67,486,592 | 47,147,080 | 114,633,672 |
| September 30 failing batch | 16,126,868 | 114,633,672 | 130,760,540 |

Each child aggregate is included exactly once in its direct parent; no arithmetic double addition was observed. Public historical bundles were reconstructed once each using the shared verified set. The different historical contexts still repeat predecessor validation work, which the current cumulative work limit deliberately counts. The September 30 context exceeds the byte cap by 2,760,540, with only four union review nodes. Historical child contexts reach six nodes; none approaches 128. The first combined rejection occurs while validating a predecessor, then the next plan and final batch gate reject the same exhausted context. All three diagnostic rejection events are byte-bound failures, not timeouts or node-bound failures.

The real replay uses 206 immutable originals (the historical cutoff selects the pre-failure subset), all 1485 Store bundle files, and four registered SHA-verified data files. All original records, metadata, bundle bytes and input data remain unchanged. The three earlier historical reconstructions return `PATH_AMBIGUOUS` for both plans; the current batch returns no bundle. This is diagnosis of the existing failure, not a successful new review or a replay credited toward natural acceptance.

Validation receipts include five telemetry/boundary methods and all 37 existing formal-review safety methods, including ancestor public-data attacks, 4096 semantic closure, 128 review-node/64 depth guards, history continuity and final-result carriers. Every check uses unchanged production limits. The standalone diagnostic source changes the publishing source identity but does not enter the formal evaluator's recursive 19-source dependency closure.
