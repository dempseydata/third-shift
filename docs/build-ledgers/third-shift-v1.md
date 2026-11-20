# Build ledger: #20 third-shift version 1 (serial) — branch night-shift/third-shift-v1

Authority: push + tracker yes · End state: branch only · Baseline: 35 tests, 51 s (first suite, set by #21; ADR 0007)

Sitting decisions: ADRs 0003–0007. Human-verified (built, left open): #27, #33, #34, #35, #36, #37, #38.

| Ticket | Status | Commit | Rounds | Suite | Notes |
| --- | --- | --- | --- | --- | --- |
| #21 | closed | (this commit) | 3 | 35 tests, 51 s | arm + next, test seam with fake gh |

## Owed
- #25: `arm` does not copy prescan.json and sitting.json into runtime state, though the spec's Records section lists them there; revival will need them (from #21 review).
- #22: `next` reads the ledger before checking the branch, so off-branch with no ledger it refuses with a bare FileNotFoundError; check the branch first (from #21 review).

## Decisions
- #21: spec slug is `<number>-<slugified title>` (bare number if the title slugs to nothing); ledger `docs/third-shift-ledger/<slug>.json` + `.md`; branch `third-shift/<slug>` — ADR? yes (hard to reverse: names the target's files and branch)
- #21: arm commit `ledger: #<spec> armed`; frontier commit `ledger: #<spec> frontier`; the script always pushes the shift branch — ADR? no (follows ADR 0005)
- #21: runtime state is `$THIRD_SHIFT_HOME/<owner>/<repo>/state.json` (default `~/.third-shift`); `next` finds the repo via `gh repo view` — ADR? no
- #21: a class in sitting.json overrides the label; every ticket, closed ones included, needs a class — ADR? no
- #21: `--ceiling none` waives the ceiling; negative ceilings refused — ADR? no
- #21: binding_sources come from sitting.json; warnings from both files — ADR? no
- #21: base moved = `git rev-parse HEAD` differs from the prescan's base commit (ADR 0005 says compare against the default branch; revisit in #30/#31) — ADR? no
- #21: at arm, a blocker outside the ticket set counts as open — ADR? no
- #21: arm refuses while runtime state says armed (one armed shift per repo) — ADR? yes
- #21: usage errors and unexpected exceptions refuse as JSON, exit 1 — ADR? no (follows ADR 0003)

## Blocked

## Nits
- #21: re-shift after a merge (ledger already tracked at base) with a failed push stages the ledger's deletion and the checkout back fails silently; restore ledger paths from base instead of rm --cached
- #21: refusal messages include absolute paths
- #21: a push that succeeds remotely but fails locally leaves a remote branch that blocks a rerun
- #21: GitHub API pagination not checked against real gh
