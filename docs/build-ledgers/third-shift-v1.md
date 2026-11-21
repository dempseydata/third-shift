# Build ledger: #20 third-shift version 1 (serial) — branch night-shift/third-shift-v1

Authority: push + tracker yes · End state: branch only · Baseline: 35 tests, 51 s (first suite, set by #21; ADR 0007)

Sitting decisions: ADRs 0003–0007. Human-verified (built, left open): #27, #33, #34, #35, #36, #37, #38.

| Ticket | Status | Commit | Rounds | Suite | Notes |
| --- | --- | --- | --- | --- | --- |
| #21 | closed | e761863 | 3 | 35 tests, 51 s | arm + next, test seam with fake gh |
| #22 | closed | bbb714b | 2 | 55 tests, 119 s | admit, step, done with commit-pinned evidence; suite past 2× baseline |
| #23 | closed | 370b4f2 | 1 | 78 tests, 99 s | needs-you, stall, release, note, wait, end; suite cut 118→61 s for old tests |
| #24 | closed | 8c31748 | 1 (nits) | 86 tests, 104 s | usage gate in admit and step --begin; pause/resume; past 2× baseline again |
| #25 | closed | ed40762 | 2 | 101 tests, 26 s | lease, heartbeat, is-dead, revive, hooks.json; tests now threaded |
| #26 | closed | 728efb1 | 1 | 118 tests, 32 s | stop-check and the Stop hook: block with work left, stall, three stalls end the shift |
| #27 | open (human-verified) | 03d43fc | 2 | 140 tests, 37 s | guard, PermissionRequest deny, refusal log; foreground-subagent deny needs a live run |
| #28 | closed | bf8427f | 2 | 157 tests, 46 s | setup-board, cards, status comment, resolution comments, close at done; round-2 one-liner checked by the orchestrator, not re-reviewed; real GitHub calls unrun (no `project` scope); first commit refused by denylist (fixture URL), issue closed before it landed, corrected |
| #29 | closed | 3e2fd44 | 2 | 165 tests, 50 s | handover rendered from the ledger, end state applied; round-2 fix checked by the orchestrator, not re-reviewed |
| #30 | closed | 417282f | 1 | 177 tests, 58 s | cli/prescan reads the ticket set; base = default branch; round-1 fix checked by the orchestrator (incl. under uv), not re-reviewed |
| #31 | closed | 310ceb5 | 1 | 203 tests, 72 s | prescan environment checks, cli/rules.json; round-1 fix checked by the orchestrator, not re-reviewed; real-tool shapes confirmed read-only |
| #32 | closed | 5a9451f | 1 | 203 tests, 64 s | role table and briefs in skills/start/references/briefs.md, new verifier brief; round-1 wording fix checked by the orchestrator |
| #33 | open (human-verified) | 8b2becd | 2 | 207 tests, 64 s | 8 eval cases, render script, FROZEN.md; not run — the first recorded run is the builder's; round-2 regex fix checked by the orchestrator |
| #34 | open (human-verified) | 7b5779f | 1 | 209 tests, 72 s | start skill: prescan, sitting, ADRs, watchman, arm; `arm --watchman`; live-only, round-1 fix checked by the orchestrator |
| #35 | open (human-verified) | 2636a6b | 1 | 220 tests, 72 s | setup skill (per machine), cli/settings; live-only; round-1 fix checked by the orchestrator |
| #36 | open (human-verified) | 059562b | 1 | 228 tests, 70 s | setup per target: board, pin, recipe drafts, proof in a scratch copy, cli/recipe; live-only; round-1 fix checked by the orchestrator |
| #37 | open (human-verified) | (this commit) | 4 | 240 tests, 70 s | the shift loop (loop.md), `ceiling`, running steps, resume_cron, inline done JSON; 3 rounds + one small round per the rules; round-4 checked by the orchestrator |

## Owed
- #25: ~~prescan.json and sitting.json copied into runtime state~~ — paid in #25.
- #22: ~~`next` checks the branch before reading the ledger~~ — paid in #22.
- #28: ~~post the resolution comment and close at done~~ — paid in #28.
- #24: ~~gate in admit and step --begin~~ — paid in #24.
- #23: ~~suite speed~~ — paid in #23 (class fixtures copied per test).
- #24: ~~suite speed~~ — partly paid in #24 (97 s at review, 104 s at commit).
- #25: ~~suite speed; `pause --until` zoned~~ — paid in #25 (104 → 26 s).
- #38: a STOP file lets the session stop but does not end the shift, and is-dead ignores STOP, so the watchman could revive it; #38's criterion "A stop file ends a shift, revived or not" owns it (from #26 review).
- #37: ~~scratch location~~ — paid in #37, superseded: after arm no Claude tool writes scratch files (`.git` is a protected path); `done --comment` takes inline JSON.
- #31: ~~fill checks, baseline, Proven commit, warnings~~ — paid in #31.
- #34: ~~prescan questions → sitting gaps~~ — paid in #34.
- #31: ~~create ADR 0006's rules file~~ — paid in #31 (`cli/rules.json`).
- #35: ~~settings from cli/rules.json; allow patterns match~~ — paid in #35.
- #36: ~~Proven section format~~ — paid in #36 (`cli/recipe proven`, tested against the real prescan check).
- #37: ~~evidence path → permalink~~ — paid in #37.
- #34: ~~Prescan usage; missing recipe~~ — paid in #34 (prescan usage not recorded, nothing is armed; a missing recipe fails `recipe proven`).
- #38: the scheduled-task tool takes no working folder, so `start revive <owner/repo>` must find the target folder from runtime state.json's `target`; the watchman's task id is in state.json (`arm --watchman`) for removal at end (from #34 review).
- #37: ~~mid-shift ceiling waiver~~ — paid in #37 (`ceiling --gen N <N|none>`).

## Decisions
- #21: spec slug is `<number>-<slugified title>` (bare number if the title slugs to nothing); ledger `docs/third-shift-ledger/<slug>.json` + `.md`; branch `third-shift/<slug>` — ADR? yes (hard to reverse: names the target's files and branch)
- #21: arm commit `ledger: #<spec> armed`; frontier commit `ledger: #<spec> frontier`; the script always pushes the shift branch — ADR? no (follows ADR 0005)
- #21: runtime state is `$THIRD_SHIFT_HOME/<owner>/<repo>/state.json` (default `~/.third-shift`); `next` finds the repo via `gh repo view` — ADR? no
- #21: a class in sitting.json overrides the label; every ticket, closed ones included, needs a class — ADR? no
- #21: `--ceiling none` waives the ceiling; negative ceilings refused — ADR? no
- #21: binding_sources come from sitting.json; warnings from both files — ADR? no
- #21: ~~base moved = HEAD differs from the prescan's base~~ — superseded in #30: the base is origin's default-branch commit, and arm compares against it (ADR 0005) — ADR? no
- #21: at arm, a blocker outside the ticket set counts as open — ADR? no
- #21: arm refuses while runtime state says armed (one armed shift per repo) — ADR? yes
- #21: usage errors and unexpected exceptions refuse as JSON, exit 1 — ADR? no (follows ADR 0003)

- #22: ticket is positional; `--gen` required on every write command including `next` — ADR? no (spec)
- #22: stale `--gen` exits 2 with `stop: true`; logging left to #25 — ADR? no (ADR 0003)
- #22: `admit` freezes nothing new: it compares the body's `## Acceptance criteria` checkboxes to the frozen list; changed criteria → Needs you, reason blocker with a why; only one ticket In progress at a time — ADR? no
- #22: commits `ledger: #<n> admitted|step|needs you|done` — ADR? no
- #22: `done` refuses any `not met` verdict, and any ticket with no frozen criteria — ADR? no
- #22: evidence must fullmatch `https://github.com/<repo>/blob/<40-hex>/<path>[#Ln[-Lm]]`, path a blob at that sha, sha an ancestor of the shift branch, no `.`/`..`/empty segments, not the ledger's own files — ADR? yes (the evidence contract the verifier brief and eval V1 depend on)

- #23: needs-you and stall only from In progress; release from any Needs you ticket, human ones included — ADR? no
- #23: release re-reads blockers (Ready or Backlog) and keeps the question beside the answer; release while waiting returns the shift to running (spec has no waiting → running move) — ADR? yes (adds a shift-state transition the spec lacks)
- #23: release, note and end commit (`released`, `<kind>`, `ended`); wait writes runtime state only — ADR? no
- #23: fast-forward end state is one atomic push of both refs; refuses and writes nothing if not fast-forwardable; disarm only after every push succeeds — ADR? no
- #23: tests run the script with the suite's Python; one test keeps `uv run --script` — ADR? no

- #24: usage readings reach the script as flags on `admit` and `step --begin`: `--5h P --reset ISO --weekly P` (repeatable; the gate takes the highest) or `--unreadable`, plus `--guess G` (the role table's starting figure) — ADR? yes (the contract #37's loop must speak)
- #24: `admit` gates as the implementer and exits 1 on any answer but proceed; `step --begin` exits 0 with any answer — ADR? no (ADR 0003)
- #24: the unreadable count persists in runtime state even when admission is refused — the one exception to "refusals write nothing" — ADR? no (spec: three failures in a row)
- #24: a reading after a window reset mid-step is the after-reading, marked `lower_bound` — ADR? no (map #6)
- #24: `pause --reason usage|owner`; pause and resume commit to the ledger — ADR? no
- #24: the gate's pause point is capped at 99% in every mode; while paused the gate answers pause-until — ADR? no (map #6)

- #25: tests run on threads via `load_tests` in tests/__init__.py, one lock per shared fixture; 104 → 26 s — ADR? no
- #25: a stale `--gen` is logged to `refusals.jsonl` in runtime state (ADR 0002 lists refusals in the ledger; a stale session cannot commit) — ADR? yes (amends ADR 0002)
- #25: heartbeat on PreToolUse records only its time; a session claims the lease only if its cwd is inside the stored `target`; revive retires the outgoing session id, which can never reclaim — ADR? yes (refines ADR 0004's lease binding)
- #25: revive refuses unless is-dead; sets work aside on `refs/third-shift/<slug>/set-aside-<gen>` and pushes it; returns the shift to running — ADR? no
- #25: is-dead never counts a waiting shift or an owner pause as dead; a usage pause is dead only after reset + 15 min (map #10) — ADR? no
- #25: a ticket in progress across two crashes → Needs you, "set aside after a crash" — ADR? no (map #15)

- #26: the Stop hook fails open: any failure exits 1 (non-blocking per the hook docs); the watchman is the backstop — ADR? yes (safety posture of the gate)
- #26: stop-check prints only the hook's fields: `{}` to allow, `{decision, reason}` to block — ADR? no (compatible with ADR 0003)
- #26: progress = the ledger file changed (map #15); the third blocked stop without progress stalls the In progress ticket; with nothing In progress it allows the stop and resets the count; `stop_hook_active` is ignored — ADR? no
- #26: the stall row is read from ledger commit messages since the last `armed`; done, needs-you and released break it; three stalls end the shift, blocking once to say so — ADR? no
- #26: the gate's "end" answer is recorded in runtime state; revive clears it — ADR? no
- #26: Backlog tickets whose blockers are all Done count as work left; stall refs `stalled-<n>-<k>` — ADR? no

- #27: a push passes only if it names a remote and every destination is `third-shift/*`; bare `git push`, HEAD and tag pushes are refused — ADR? yes (stricter than the spec's "no default-branch push")
- #27: all three safety hooks log refusals to the ledger's `refused` list in a `ledger: refused` commit, falling back to refusals.jsonl off-branch or when the push fails; commands are redacted (key shapes, secret args) and cut to 500 chars — ADR? no (ADR 0002)
- #27: the guard fails closed on an unreadable command and on an unreadable state.json for the session's own repo; malformed hook stdin fails open — ADR? yes (the guard's safety posture)
- #27: only `uv run --script <plugin>/cli/shift` is exempt from the outside-the-repo rule; the rest of the plugin root is refused; a quoted word is a path if it starts with `~` or it or its parent exists — ADR? no
- #27: every state.json write is atomic (per-process temp + os.replace) — ADR? no
- #27: stop-check does not count a refusal as progress — ADR? no

- #28: `setup-board --spec N` is required, idempotent and takes no `--gen` (it runs before arm); the Spec option and view are named `#N <title>`; the view's filter is set by a second mutation — ADR? no
- #28: board ids cached in `board.json` in runtime state, kept only while the board id matches; drawn state under `mirror` in state.json — ADR? no (ADR 0006)
- #28: a failed mirror write does not fail the command: it reports `mirror: behind` and the next mirroring command catches up; a resolution comment whose reply was lost can be posted twice — ADR? yes (the ledger-first, mirror-behind posture)
- #28: with no board, comments still post and done still closes; only cards are skipped (`mirror: behind: no board`) — ADR? no
- #28: target folder → `.`, home → `~` in comments and Why — ADR? no

- #29: the handover is `<slug>.handover.md` beside the ledger; findings, candidates and added sub-issues are stored in `ledger["end"]` so it renders from the ledger alone — ADR? no (ADR 0002)
- #29: refusals logged off the ledger (refusals.jsonl) are read into `ledger["end"]` at end and counted with the ledger's; a successful arm archives the old log as `refusals.<UTC>.jsonl` — ADR? no
- #29: an unreadable tracker reads "Unknown"; stalled and unreached tickets list under Needs you; Done rows link each criterion's evidence directly — ADR? no

- #30: cli/prescan loads cli/shift as a module (bytecode writes off) so criteria, slug and gh calls cannot drift; `--out` is required — ADR? no
- #30: both triage labels, neither, a cycle, a self-edge, or a `## Blocked by` entry without a native link become questions; criteria accept `-`, `+`, `1.` and `1)` checkboxes and skip blank ones — ADR? no
- #30: the prescan refuses while an unmerged `third-shift/<slug>` exists, local or remote (ADR 0005) — ADR? no

- #31: the power check carries `mode: away`; arm skips a failed check for the other mode, and a battery in day mode is a warning — ADR? no (map #18)
- #31: recipe unchanged = its `## Proven` section names a commit where the recipe (minus that section) and `playwright.config.*` match today — ADR? yes (a file format setup and the prescan share)
- #31: the guard counts as active when any `third-shift@*` key in `enabledPlugins` is true; scopes read with `gh auth status --json`, `project` and `repo` required — ADR? no (ADR 0006, map #3)
- #31: `verify/checks` is timed into the baseline, bounded at 600 s (`THIRD_SHIFT_CHECKS_TIMEOUT`); on timeout SIGTERM to the group, a grace period, then SIGKILL; chromium, ffmpeg and headless-shell must carry `INSTALLATION_COMPLETE` — ADR? no
- #31: the push dry-run uses `--no-verify` so the target's pre-push hook never runs — ADR? no

- #32: starting costs in points of the 5-hour window — Prescan 5, Implementer 6, Reviewer 5, Fixer 3, Verifier 3 — guesses set high on purpose (a high guess only pauses early) — ADR? no
- #32: scratch files live under `.git/third-shift/` (never committed; the guard allows it) — ADR? no
- #32: verifier files `e2e/<n>-<k>.spec.ts`, evidence under `verify/evidence/<n>/` (`<k>.png`, `report.json`, `<k>-steps.md`; a needs-your-run criterion gets a steps file, since done refuses a row without evidence) — ADR? yes (the evidence layout the eval set and targets depend on)
- #32: reviewers treat an unpaid owed entry and an unsettled hard-to-reverse decision as must-fix; implementers build test-first with `tdd` (the `implement` skill is user-invoked only) — ADR? no

- #33: fixtures live inside each case (the eval tool refuses map #19's shared `evals/fixtures/`); rendered prompts are generated and git-ignored (they hold absolute `add_dirs` paths) — ADR? yes (departs from map #19)
- #33: cases allow read-only Read, Glob, Grep (listing is not a grant), with a `tool_used: Bash, max: 0, min: 0` guard; model per the role table; Haiku judge; 30 turns, 900 s — ADR? no
- #33: the tool cannot express 2-of-3 / 3-of-3 pass marks; each case states its mark and the builder judges from per-run results; the first run is recorded in committed `evals/FROZEN.md`, raw output kept in ignored `local-data/` — ADR? no

- #34: any failed check except mains power stops `start` before the prescan brief; the prescan step's usage is not recorded — ADR? no
- #34: the sitting's ADRs and the watchman are made BEFORE arm (after arm the session's own prompts are denied); a refused arm deletes both; class/edge questions sit in sitting.json with `"adr": null` — ADR? yes (the start sequence is forced by the PermissionRequest deny)
- #34: the watchman runs every 15 min with prompt `/third-shift:start revive <owner/repo>`, `notifyOnCompletion` false; the id the tool returns is stored via `arm --watchman <id>` (ADR 0004) — ADR? no

- #35: setup writes `permissions.blockWritesOutsideWorkingDirectories: true` (map #4, never amended) and the prescan checks it; it also binds the builder's attended sessions, the trade-off that dropped `denyInsteadOfPrompting` (map #9) — ADR? yes (builder may want to drop it)
- #35: `Skill(third-shift:start *)` added beside the bare form, from the docs only (map #17 saw no prompt for a hook-less skill) — ADR? no
- #35: cli/settings shows missing rules by default; `--write` appends them, keeps everything else, keeps the file's mode and symlink, refuses unreadable or read-only files, atomic — ADR? no
- #35: the builder types `! gh auth refresh -s project` (browser sign-in); the Mac checklist runs first, so the Remote Control refusal and a missing uv refuse before any edit — ADR? no

- #36: setup makes two commits, `third-shift: setup` then `third-shift: setup proven`, where the ticket says one: the Proven line cannot name the commit that holds it (forced); a PR must be merge-committed, not squashed; PR branch `third-shift/setup` — ADR? yes (departs from the ticket's wording)
- #36: `cli/recipe pin` picks the newest released `@playwright/test` whose chromium is installed (assumes revisions grow with versions); setup asks for a spec number for setup-board; drafts `e2e/setup.spec.ts` as the proving test — ADR? no
- #36: the deliberate break runs in an rsync copy under `.git/third-shift/prove` (map #16: a scratch copy), removed on every path; Proven is recorded only when this run proved it — ADR? no

- #37: `step --begin` (and `admit` on proceed) mark a step running in runtime state; while set, stop-check allows stops and counts nothing toward a stall; the step record, `leave` and `revive` clear it — ADR? yes (how the Stop gate coexists with backgrounded subagents)
- #37: `wait` refuses only while the frontier is non-empty; Backlog behind Needs you does not block waiting — ADR? no
- #37: gate answers carry `resume_cron` (local time, reset + 3 min) and `now`, so the loop runs no `date`/`python -c`; resumes use a one-off CronCreate (session-only, fires when idle) — ADR? no
- #37: after arm no Claude tool writes under `.git/` (protected path, prompts refused); `done --comment` takes inline single-quoted JSON, or `-`/a file — ADR? yes (supersedes #32's post-arm scratch convention)
- #37: blockers and stalls set work aside on named refs; a released ticket is rebuilt from scratch; "retry" is a short pause plus timer; a `not met` verdict spends a fix round; two failed spawns stall a ticket; `--tokens 0` when none reported — ADR? no
- #37: rules.json gains `git rev-parse *`, `mkdir -p .git/third-shift*`, `npx playwright test*`, `playwright-cli*`, `./verify/checks`; setup step 13 adds the target's own test and launch commands via `cli/settings --allow` — ADR? no

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
- #23: releasing a human ticket sends human work to the agent frontier
- #23: the kill test's assertions would also pass on a plain push failure
- #23: refusal messages include temp paths
- #24: a window reset whose after-reading is ≥ the before-reading goes undetected
- #24: a single `--weekly` reading is accepted
- #25: `cli/shift` ~560 `state["target"]` raises KeyError on a parseable state.json with no target
- #25: malformed hook stdin is refused before the armed check
- #25: the threaded runner skips setUpClass/module fixtures and ignores failfast and `-b`
- #25: tests/test_revival.py ~98 comment claims glob order is sorted
- #26: the `armed` and `released` stall-row breaks have no committed test
- #26: the Stop hook's timeout behaviour not checked
- #27: with a corrupt state.json and `gh repo view` failing (no origin, offline), Bash is denied in that repo for every session; match `git remote -v` URLs instead
- #27: a deleted hook cwd with a corrupt state fails open (exit 1) even inside the owning repo; catch OSError
- #27: passes: `python -c`, `base64 | sh`, aliases, a symlink already in the repo, writes to `.git/config`, `gh workflow run`
- #27: `grep "/api"` is now refused (fails safe)
- #27: PermissionDenied's exact payload and the guard's hook-timeout behaviour not checked
- #28: a stall from stop-check is not mirrored until the next command
- #28: a card deleted by hand leaves a stale item id
- #28: no GraphQL mutation has run against real GitHub; shapes checked only by schema introspection
- #29: two successful arms in the same second would overwrite the first refusal archive
- #29: the per-ticket usage table ignores `lower_bound`
- #30: a shift branch merged on the remote but not fetched refuses with a misleading "not merged"
- #30: criteria after a `###` heading inside the criteria section are dropped
- #30: a node between two cycles is named as "in" a cycle
- #30: real gh pagination and the dependencies API shape unchecked
- #31: when the settings `model` key is unset, the model warning appears on every run
- #31: a webServer the Playwright runner never stops (detached, own group) is beyond the timeout's reach
- #31: GH_TOKEN with a classic token not checked
- #32: long lines in briefs.md not re-wrapped
- #33: R1's regex still passes a CLEAN verdict that mentions MUST-FIX without "no" just before it (the LLM rubric is the backstop)
- #33: wrong answers some regexes still pass (P1 "no gaps" listing the tickets; single-line P5/P6) — the rubric must catch them
- #33: V1's evidence PNGs are 1×1 pixel
- #33: how `plugin eval` combines regex and rubric graders into one run's pass is unchecked
- #34: whether `update_scheduled_task` (used when a stale watchman id is in use) returns an id is unchecked
- #35: a dangling settings symlink creates the folder it points to
- #36: a rerun after a failed proof refuses because of setup's own uncommitted drafts
- #36: whether `blockWritesOutsideWorkingDirectories` blocks npm's cache writes is unchecked
- #37: a `> report.json` redirect after `npx playwright test` still prompts in default permission mode (Edit check on the target)
- #37: whether `get_usage` (an MCP tool) prompts mid-shift is unverified
- #37: whether the Stop hook fires while a background agent runs is unverified live
