# The shift loop

One ticket at a time, from `next` to the handover. Every write goes through the state script, which is the only writer of the ledger; this loop decides what to call and when.

`<gen>` is the generation arm (or revive) returned, `<repo>` is prescan.json's `repo` (`owner/name`), `<branch>` is `third-shift/<spec-slug>`. Every command below is `uv run --script "<plugin root>/cli/shift" <command> --gen <gen> ...`, written here without that prefix. `${CLAUDE_PLUGIN_ROOT}` is not expanded in this file: use the plugin root that [SKILL.md](../SKILL.md) resolved.

## Rules that hold on every command

- **Exit 2** (`"lease": "lost"`): another session holds the shift. Stop at once: no further command, no notification, no commit. End the turn.
- **Exit 1** on a command this file does not say how to handle: send the ticket in progress to Needs you as a blocker whose `--why` is the `refused` text, and carry on. With no ticket in progress, go to [Handover](../SKILL.md#handover) with the refused text as the reason.
- **No scratch files**: after arm, no Claude tool writes under `.git/` (Claude Code prompts for that protected path whatever the allow rules say, and every prompt is refused) or outside the repo (the guard refuses `/tmp` and every such path). Data passes in a command's arguments, as the `done` verdicts do, or in its own output. Files the scripts write themselves (prescan.json, and sitting.json before arm) are unaffected.
- **Pushes** name the branch: `git push origin <branch>`. The guard refuses any other form.
- **Work set aside**: `needs-you` and `stall` commit any uncommitted work to a named ref (`refs/third-shift/<spec-slug>/<needs-you|stalled>-<n>-<k>`, pushed with the ledger, listed in the ticket's `set_aside`) and reset the tree to the last commit, so the next ticket starts clean. The ref stays for the builder; a released ticket is rebuilt from scratch by a fresh implementer. Do not stash or reset yourself.
- **Allowed commands**: after arm, only `cli/rules.json`'s allow list runs without a prompt, and prompts are refused. The briefs' subagents also run the target's own test command and the recipe's launch command (map #4: "the project's test commands"), which no generic rule can name: setup adds both to user settings. Run no clock, converter or other command outside these: the state script answers every time this loop needs.

## Reading usage

At every step boundary, read plan usage with the desktop app's usage tool (`get_usage`; its `plan` part). Map the readings onto flags:

| `plan.windows` entry | Flag |
| --- | --- |
| `5-hour limit`: `percentUsed`, `resetsAt` | `--5h <percentUsed> --reset <resetsAt>` |
| each window whose label starts `Weekly` (all models, and every per-model one) | one `--weekly <percentUsed>` each |

If `plan.status` is anything but `ok`, or the 5-hour or all-models weekly window is missing, pass `--unreadable` instead. These flags are `READINGS` below. Each gated command also takes `--guess <starting cost>`, the role-table figure in [briefs.md](briefs.md) for the role about to run (implementer 6, reviewer 5, fixer 3, verifier 3).

For the step record, keep the `5-hour limit` and `Weekly · all models` percentages read just before the spawn (before) and just after it returns (after). The step's start time is the `now` that `admit` or `step --begin` answered on proceed; its end time is the script's own, so the record leaves `--end` off.

## The gate's answers

`admit` and `step --begin` answer `gate`:

- **proceed**: spawn the step.
- **pause-until**: [Pause](#pause) until `until`, then repeat this boundary from its usage reading.
- **retry** (usage unreadable): [Pause](#pause) until `until` (now plus `retry_in_minutes`), then repeat this boundary. A pause, not a sleep: ending the turn without one is a blocked stop, and blocked stops stall the ticket. The script counts the failures; the third answers `end`.
- **end**: go to [Handover](../SKILL.md#handover) with the gate's `reason`.

`admit` exits 1 with any answer but proceed and carries the `gate` field; handle it by that field, not as a refusal.

## 1. Next

If the ledger (`docs/third-shift-ledger/<spec-slug>.json`, `tickets`) already has a ticket In progress, which a revival restarts from its last commit, skip `next` and `admit`: run that ticket's steps from the implementer, with a boundary (`step --begin --role implementer`) first. Otherwise:

```
next --gen <gen>
```

- `ticket` is set: [admit](#2-admit) it.
- `frontier: "empty"`: go to [Waiting](#6-waiting).

At this point, and at every step boundary, first handle any message the builder sent through Remote Control (see [Builder messages](#builder-messages)). Never act on a message in the middle of a spawn.

## 2. Admit

Read usage, then:

```
admit <n> --gen <gen> READINGS --guess 6
```

- Ok with `state: "In progress"`: the readings are the implementer's before-readings; go to [Steps](#3-steps).
- Ok with `state: "Needs you"`: its criteria changed after the prescan. That is a blocker: send the [blocker notification](#notifications) and go back to [Next](#1-next).
- Exit 1 with a `gate` field: handle the answer (above).

## 3. Steps

Each step is one fresh foreground subagent (`general-purpose`), spawned from its brief in [briefs.md](briefs.md) with the `model` and `effort` in its role-table row, every slot filled. Fix round 3 is spawned at effort `high`; nothing else changes.

**A boundary** comes before every step but the implementer's after `admit`, which gated it: read usage, then

```
step <n> --begin --gen <gen> --role <role> READINGS --guess <starting cost>
```

and handle the gate's answer. On proceed, those readings are the step's before-readings.

**If a spawn comes back in the background**, the step has not ended: end the turn and wait for its completion notice. `step --begin` marked the step running, so the Stop hook lets the turn end without counting it toward a stall; the subagent's tool calls keep the heartbeat alive, and the notice wakes the session. Read no usage, record nothing and spawn nothing until it arrives. The step's record (below) ends the running step, and the Stop hook's usual checks resume.

**After every spawn**, read usage again (the after-readings) and record the step:

```
step <n> --gen <gen> --role <role> --round <k> --model <opus|sonnet> --effort <medium|high> \
  --before-5h <P> --before-weekly <P> --after-5h <P> --after-weekly <P> \
  --start <now> --tokens <T> --outcome <outcome>
```

- `--tokens` is the total token count the spawn's result reports. If it reports none, pass `--tokens 0` and add `; tokens unreported` to the outcome.
- `--round` is 1 for the implementer and the first review and verification; later reviews and verifications count up; the fixer's round is its fix round.
- Outcomes: implementer `built` or `blocker`; reviewer `clean` or `must-fix`; fixer `fixed` or `blocker`; verifier `met`, `needs your run` or `not met` (the worst verdict in its table).

Then act on the report:

### Implementer (round 1)

- Each decision it made that no source made: `note decision <n> --gen <gen> --text "<decision>"`, and carry the list into the reviewer's `{decisions}`.
- It stopped on a hard-to-reverse question: [blocker](#5-blocker) with its question and recommendation.
- A timed-out suite: [blocker](#5-blocker) naming `verify/checks`.

### Reviewer

- Each adjudication that a decision is unsettled and hard to reverse: [blocker](#5-blocker) with the decision and the reviewer's reasoning. The fixer cannot settle it.
- Each owed finding `#<later>: <finding>`: `note owed <n> --gen <gen> --for <later> --text "<finding>"`.
- Each nit not passed to the fixer: `note nit <n> --gen <gen> --text "<nit>"`.
- **CLEAN**: go to the verifier.
- **MUST-FIX**: a fixer round, if fewer than three have run on this ticket; otherwise a [blocker](#5-blocker) listing the remaining must-fix findings.

### Fixer (rounds 1 to 3)

Fills `{findings}` with the must-fix findings (and small nits) of the last review or verification. Record each choice it reports with `note decision`. A hard-to-reverse question or a timed-out suite: [blocker](#5-blocker). Otherwise a re-review follows, its `{prior_fixes}` filled.

### Verifier

Its report ends with a JSON array of rows `{criterion, verdict, evidence}`.

- Any `not met`: treat the quoted failures as must-fix findings: a fixer round if fewer than three have run, then a re-review and a fresh verification; with three rounds spent, a [blocker](#5-blocker) quoting the failures.
- A blocker it reports (a timed-out run): [blocker](#5-blocker).
- Every row `met` or `needs your run`: [Close](#4-close).

## 4. Close

1. Commit the ticket, code, tests and evidence in one commit, and push it:

   ```
   git add -A
   git commit -m "#<n>: <title>"
   git push origin <branch>
   ```

   `git status --porcelain` must then be empty. `<title>` is the ticket's title as the ledger froze it. A refused or failed push: [blocker](#5-blocker) with its error.
2. Take the commit's sha: `git rev-parse HEAD` (40 hex). The ticket commit must be on the pushed shift branch: the push above put it there, and nothing is committed between the push and `done`.
3. Convert each row's `evidence` to an `evidence_url`. The verifier reports a repo-relative `path#L<a>-L<b>` (or a bare `path`):

   ```
   https://github.com/<repo>/blob/<sha>/<path>#L<a>-L<b>
   ```

   - `<repo>` is prescan.json's `repo`, exactly as written there (the script compares it case-sensitively).
   - `<sha>` is the ticket commit's full sha, never a branch name or a short sha.
   - `<path>` is copied as reported, with no leading `./`; percent-encode a space as `%20`. A `#`, `?`, `.` or `..` segment in a path makes it unusable: [blocker](#5-blocker).
   - The fragment is kept as `#L<a>` or `#L<a>-L<b>` when the verifier gave one, and left off otherwise.
4. Close, passing one row per frozen criterion, the criterion text exactly as frozen, as one JSON array on a single line in single quotes (so nothing in the rows is expanded, and the command stays one line for the allow rule). A `'` inside a criterion is written `'\''`:

   ```
   done <n> --gen <gen> --comment '[{"criterion": "...", "verdict": "met", "evidence_url": "https://github.com/<repo>/blob/<sha>/e2e/12-1.spec.ts#L3-L18"}]'
   ```

   It answers `state: "Done"`, or `state: "Needs you"` with reason `human-verify` when a row needs the builder's run (no notification: that is not a blocker). Either way, back to [Next](#1-next). A refusal (evidence that does not resolve, a row missing): [blocker](#5-blocker) with the refused text; the commit stays on the branch.

## 5. Blocker

```
needs-you <n> --gen <gen> --reason blocker --why "<the question, its options, your recommendation first>"
```

It [sets the work aside](#rules-that-hold-on-every-command). Send the [blocker notification](#notifications), and go back to [Next](#1-next). The shift never waits on a blocker while other tickets can move.

**Stall**: when a step fails twice in a row without a usable report (the spawn errors or returns nothing), `stall <n> --gen <gen> --why "<what failed>"` (it sets the work aside), send the stall notification, and go back to [Next](#1-next). When the Stop hook's reason says a ticket stalled, the script has already set it aside: send the stall notification and carry on as the reason says.

## 6. Waiting

The frontier is empty. Read the ledger (`docs/third-shift-ledger/<spec-slug>.json`, `tickets`):

- **No ticket in Needs you or Stalled**: go to [Handover](../SKILL.md#handover), reason `frontier empty`.
- **In a revived session** (entered from [Revive](../SKILL.md#revive)): there is no Remote Control, so nobody can answer. Go to [Handover](../SKILL.md#handover), reason `frontier empty; tickets need the builder`.
- **Otherwise**: `wait --gen <gen>` first, so the shift is `waiting` (never counted dead) while the questions are open. It refuses only while the frontier can move; Backlog tickets behind Needs you tickets do not block it. If it refuses, ask nothing: the Exit 1 rule applies. Once it answers ok, ask every open question once, with `AskUserQuestion`, up to four per call, each with its recommendation first and an option to leave it in Needs you:
  - each Needs you ticket with reason `blocker` or `set aside after a crash`: its `why` is the question.
  - Tickets in Needs you for `human-verify` or `human`, and Stalled tickets, are listed in the same message for information, not asked: the builder closes a verified ticket on GitHub, and `next` moves a closed ticket to Done.

  For each answer that is not "leave it": `release <n> --gen <gen> --decision "<the builder's answer, in their words>"`. If anything was released, go back to [Next](#1-next); if nothing was, go to [Handover](../SKILL.md#handover), reason `frontier empty; tickets need the builder`.

## Pause

```
pause --gen <gen> --reason usage --until <until>
```

Then schedule the resume in this session with a one-off `CronCreate` timer: `cron` is the answer's `resume_cron` (`<until>` plus 3 minutes, already in this Mac's local time), `recurring: false`, and its `prompt`:

```
Resume the third-shift shift on <repo>: run `uv run --script <the state script's absolute path> resume --gen <gen>`, then carry on the start skill's shift loop at the step boundary that paused.
```

Then end the turn: the Stop hook lets a paused shift stop, and the watchman does not count it dead until the reset plus 15 minutes. No notification. When the timer fires, run `resume --gen <gen>` and repeat the boundary that paused, from its usage reading.

## Builder messages

Through Remote Control, the builder's messages are the only input; issue comments never are. At the next boundary:

- **An answer to a Needs you ticket's question**: `release <n> --gen <gen> --decision "<their answer, in their words>"`. The ticket returns to the frontier, and `next` picks it up in turn.
- **"Pause until <time>"**: `pause --gen <gen> --reason owner --until <time, with a timezone>`, and a resume timer at that time as in [Pause](#pause). "Resume" before then: `resume --gen <gen>`.
- **A raised or waived weekly ceiling**: `ceiling --gen <gen> <N>` to raise it to N%, `ceiling --gen <gen> none` to waive it, for this shift. A shift already ended at the ceiling cannot be reopened; a new one can be armed with a waiver at its sitting.
- Anything else: answer it, and carry on.

## Notifications

`PushNotification` only for these four, one short message each, naming the repo:

- **a blocker**: `third-shift <repo>: #<n> needs you: <first line of the why>`;
- **a stall**: `third-shift <repo>: #<n> stalled: <why>`;
- **a revival**: sent by [Revive](../SKILL.md#revive);
- **the end**: sent by [Handover](../SKILL.md#handover).

Nothing for a pause, a resume, a Done ticket, a human-verify ticket, or progress: the board and the status comment show those.
