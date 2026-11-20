# Keep the ledger in the target project and runtime state on the Mac

The state script writes two kinds of record, and they live in different places. The ledger (ticket states, decisions, owed findings, nits, refusals, per-ticket usage, crash counts) is committed in the target project under `docs/third-shift-ledger/`, as JSON that only the script writes, with a generated markdown copy and the handover beside it. The script commits it in its own `ledger:` commits, because a ticket's commit can't contain its own commit id. Runtime state (whether the shift is armed, the heartbeat, the lease generation, pause and reset times, the revival count, cached board ids) stays on the Mac, outside every repo.

We considered keeping everything local, so that no record of a shift reached GitHub at all. We rejected it because the builder wants the build record kept with what was built. We considered committing everything to the shift branch, and rejected that too: the heartbeat changes on every tool call, and pauses would each need a commit. The third-shift repo itself never holds run data, only tooling.

## Consequences

- Who can see a shift's ledger, evidence, status comment and board is decided by the target repo's visibility, not by third-shift.
- Losing the Mac loses runtime state but not the ledger, which is enough to start a fresh shift. Revival is already tied to this Mac (ADR 0001).
