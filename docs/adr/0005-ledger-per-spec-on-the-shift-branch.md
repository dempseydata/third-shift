# One ledger per spec on the shift branch, pushed by the script; an unmerged shift branch blocks a rerun

The target's ledger is one JSON file per spec under `docs/third-shift-ledger/` (ADR 0002), committed on `third-shift/<spec-slug>`. The state script pushes after each `ledger:` commit, so evidence permalinks in public comments resolve. The sitting's ADRs are committed on the shift branch too, and the prescan's clean-start check compares the base against the default branch.

The prescan refuses a spec while an unmerged `third-shift/<spec-slug>` branch exists: its tickets may be closed while their code is not on the default branch, and a second shift would treat them as Done.

We considered committing the ledger to the default branch (rejected: the guard refuses default-branch pushes while armed) and continuing on an existing branch (rejected: it blurs what Done means across shifts).
