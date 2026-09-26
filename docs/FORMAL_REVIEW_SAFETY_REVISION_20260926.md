# Formal review candidate safety revision 2

This is an isolated, uninstalled maintenance candidate. The earlier frozen
candidate and its failed review remain valid historical evidence. Its original
manifest is `docs/formal-review-candidate.json`; this revision uses a separate
manifest and never rewrites that receipt.

The original two defects are reproduced against preserved bytes: renaming both
SOURCE and PRIVATE attachments while changing the evaluator label, and adding a
nested `coverage.raw_prices` field. Both escaped through a newly prepared review's
single-root archive and the actual generic snapshot builder. The new candidate
rejects both before any new public root or outbox is produced. The executable
comparison and captured results are in `tests/replay_formal_public_safety.py` and
`tests/receipts/formal-public-safety-replay-20260926.json`.

The new gate identifies every reached review bundle using METHOD and full
approved source identity. It reconstructs the historical complete public batch
from its original availability time, frozen visible store and retained private
requests. It compares entire records, including all nested fields, and the
explicitly permitted attachment bytes. Unknown layouts and identities cannot
bypass this gate. Renaming files is not a proof of publication permission.

The first manual review's five original records and three permitted attachments
are bound to their original hashes. The two approved waiting profiles use the
installed, hash-bound waiting generator in a private globals namespace with
only the verified method material bound to its historical profile. No bundled
Python is executed, no module global is patched, and no request can select a
backend. Old 7db source files remain unchanged.

Historical reconstruction caches are separate from economic replay caches.
They share the validation deadline and contribute to the combined byte budget;
successful privacy reconstruction cannot warm the economic predecessor cache
and bypass a later chain limit.

Failures in new input or unsupported rules retain per-plan dispositions. A
previous minimal failure is reconstructed using only the known failure record
shape, finite reason/migration vocabulary, fixed source identity and SHA-256
input fingerprint. It can be referenced while other safe plans continue.
Three strictly bounded scalar integrity discrepancies remain per-plan failures:
method hash, private-computation hash, and inventory in {null, 0, 0.01, -0.01}.
They are normalized only in an in-memory privacy comparison; original records
are never changed, and the economic validator still rejects them.

Missing private proof, revoked historical source capabilities, and fabricated
historical prefixes no longer produce a descendant public failure bundle. They
stop before a new public root because the ancestor's complete public projection
cannot be proven. Tests explicitly document this stricter admission boundary.
This is not an economic rule change: plan windows, costs, FINAL criteria and
actual-net requirements are unchanged. Synthetic FINAL fixtures remain isolated.

The prior frozen new files and manifest are retained in a local archive with
SHA-256 `93ea2b74ab4265f8ad94a5801b274d4776cec536a52708e7a5cc265619383620`.
The matching sixteen unchanged base sources are separately retained with SHA-256
`1e3c0bd88bea154e71931c8246219df74570c749d55ac1f70e94decf1aa6949d`.
These are local engineering preservation artifacts, not uploaded research data.

Independent review and installation approval are still required. No production
review, task dispatch, source installation or publication was performed here.
