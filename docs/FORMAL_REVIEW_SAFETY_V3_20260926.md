# Formal review safety candidate revision 3

This is the current isolated candidate; revision 2 remains an intermediate,
uninstalled historical checkpoint. The complete design and two original attacks
are described in `FORMAL_REVIEW_SAFETY_REVISION_20260926.md`.

Revision 3 adds the next-batch continuation case for registered unsupported
plans. They remain `RULES_INCOMPLETE`, preserve the real cutoff and bounded input
fingerprint, and do not prevent supported plans from progressing. Such plans have
no private calculation request to recover. Their cutoff is parsed and bounded by
the original information time and predecessor cutoff; their input fingerprint
must be a SHA-256. Every other public field must still match the trusted generated
record. This also covers explicitly supplied configurations that the unsupported
plan did not evaluate. No input contents or evaluator choice are recovered from
the fingerprint.

Revision 2's frozen bytes are retained locally in an archive with SHA-256
`df5794c00bd5e4f9b3b51fd862d5faefa065dfa9f750d1f744e33c260c5b9b3f`.
Its manifest has SHA-256
`ab244754804cb027d821cfc946fa24e9c638cc26082de2a9c0ede64392434fd1`.
Neither historical receipt was rewritten.

Current source identity and actual author checks are recorded in
`formal-review-candidate-safety-v3.json`. The v2 real-source decode receipts remain
historical; there is no new production economic result or new validator capability.
The current dual-attack replay receipt is
`../tests/receipts/formal-public-safety-replay-v3-20260926.json`.

Independent approval is pending. This work changes no production source,
installation, plan, original record, role, permission, frequency or publication.
