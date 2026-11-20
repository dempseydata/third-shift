# Build ledger: #20 third-shift version 1 (serial) — branch night-shift/third-shift-v1

Authority: push + tracker yes · End state: branch only · Baseline: 35 tests, 51 s (first suite, set by #21; ADR 0007)

Sitting decisions: ADRs 0003–0007. Human-verified (built, left open): #27, #33, #34, #35, #36, #37, #38.

| Ticket | Status | Commit | Rounds | Suite | Notes |
| --- | --- | --- | --- | --- | --- |
| #21 | closed | e761863 | 3 | 35 tests, 51 s | arm + next, test seam with fake gh |
| #22 | closed | (this commit) | 2 | 55 tests, 119 s | admit, step, done with commit-pinned evidence; suite past 2× baseline |

## Owed
- #25: `arm` does not copy prescan.json and sitting.json into runtime state, though the spec's Records section lists them there; revival will need them (from #21 review).
- #22: ~~`next` checks the branch before reading the ledger~~ — paid in #22.
- #28: `done` renders the closing comment but neither posts it nor closes the issue; no ticket owns closing the issue — #28 should post the comment and close (from #22 review).
- #24: `admit` applies no usage gate yet; the spec's table puts the gate in admit, ADR 0003 adds `step --begin` (from #22 review).
- #23 (next implementer): the suite is 119 s, past twice the 51 s baseline. Move tests that don't need a temp repo + bare remote + push onto the cheapest seam that still proves the same thing (e.g. shared one-time fixture repo per class, or fewer push round-trips).

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

- #22: ticket is positional; `--gen` required on every write command including `next` — ADR? no (spec)
- #22: stale `--gen` exits 2 with `stop: true`; logging left to #25 — ADR? no (ADR 0003)
- #22: `admit` freezes nothing new: it compares the body's `## Acceptance criteria` checkboxes to the frozen list; changed criteria → Needs you, reason blocker with a why; only one ticket In progress at a time — ADR? no
- #22: commits `ledger: #<n> admitted|step|needs you|done` — ADR? no
- #22: `done` refuses any `not met` verdict, and any ticket with no frozen criteria — ADR? no
- #22: evidence must fullmatch `https://github.com/<repo>/blob/<40-hex>/<path>[#Ln[-Lm]]`, path a blob at that sha, sha an ancestor of the shift branch, no `.`/`..`/empty segments, not the ledger's own files — ADR? yes (the evidence contract the verifier brief and eval V1 depend on)

## Blocked

## Nits
- #21: re-shift after a merge (ledger already tracked at base) with a failed push stages the ledger's deletion and the checkout back fails silently; restore ledger paths from base instead of rm --cached
- #21: refusal messages include absolute paths
- #21: a push that succeeds remotely but fails locally leaves a remote branch that blocks a rerun
- #21: GitHub API pagination not checked against real gh
- #22: a non-object row in the done comment file refuses with the raw AttributeError text
- #22: a symlink in the tree passes as a blob, so counts as evidence
- #22: comparing naive and aware times refuses with a raw TypeError message
- #22: a newline in a criterion breaks the rendered comment table
- #22: repo name must match case exactly in evidence links
- #22: role `prescan` can never pass the In progress check in `step`
