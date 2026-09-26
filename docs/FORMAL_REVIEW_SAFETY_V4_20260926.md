# Formal review safety candidate revision 4

This revision addresses the sole P2 finding in independent receipt
`formal-safety-independent-v3-20260926.json`, SHA-256
`c7c5db65d2855b4ca16d69391bb676ed84db1dd9096486f5285f453777ed2557`.
Repair dispatch: `repair-v3-c7c5db65d285`.

Both public-ancestor passes now use the dedicated
`MAX_SEMANTIC_ANCESTORS = 4096`. The existing 128 distinct review-node bound and
64 active review-depth bound remain unchanged. Plans, rounds, feedback and other
non-review references do not consume the review-history node limit merely by
being visited in the semantic closure. The whole-record reconstruction,
attachment byte checks, separate reconstruction caches, combined cache budget
and deadline checks are unchanged.

New regression cases use a real temporary Store to prepare and commit a complete
129-plan batch with only two prior reviews: two ordinary missing-data results
and 127 explicit `RULES_INCOMPLETE` dispositions, with no missing items. Separate
real committed evidence sets exercise 4095 and 4096 semantic nodes successfully
and reject 4097 nodes. The limits are not lowered for these tests.

A focused recursive-guard test verifies 128 distinct review nodes and 64-depth
acceptance, and rejects node 129 and depth 65. Its expensive inner validator is
explicitly replaced by a deterministic recursive stub; this is a budget-guard
test, not a claim of 128 complete economic replays. Existing full Store chain,
outbox, FINAL reuse, cache-limit and public-safety tests continue to cover those
separate behaviors.

The frozen v3 source, test and manifest remain locally preserved in an archive
with SHA-256
`93c9f00976af0e369b6abaa8ada078ed086e3524fe809c974dd6c95fe6dde321`.
No prior candidate or independent receipt was overwritten.

`formal-review-candidate-safety-v4.json` records the complete publishing source
hash (`scripts/publish.py --source-hash`) separately from the 19-file method
source-map hash and runtime-bound method hash. They are different identities and
must not be substituted for one another during installation.

Author regression results do not constitute independent approval. This remains
uninstalled engineering work. No production original, plan, operation state,
source installation, permission, scheduler or public repository was changed.
