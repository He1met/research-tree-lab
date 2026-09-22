# Approved waiting source fixture

These are test-only own-project source bytes from approved Git tree
`9a5259b7c72c1b3d40ad4b11ae2e28210252d9a0`, not a production review or runtime loader.
`contracts.py.txt` is the exact old contracts source with SHA-256
`60a65556a02328b309f016a602ba142b887d23771556a907ecce2b71144c6041`.
`METHOD.template.json` preserves the original complete method template except
created/available timestamps, which temporary-Store synthetic tests supply.
Its source/runtime identity is
`d21b004a0efe4295f391a3f82ccba05f6a967b9205d370eabd807a8692f91f65`.

The other five actually bundled source files are unchanged; tests read their
repository bytes only after matching each original hash. No test invokes Git,
network, or executes record attachment code. Thus shallow CI checkout is enough.
The approved helper attached six sources while its METHOD bound eleven static
dependencies; this fixture does not claim a self-contained full method archive.
