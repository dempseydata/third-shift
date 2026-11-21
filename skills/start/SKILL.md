---
name: start
description: Start a third-shift shift on a spec's sub-issues (prescan, decision sitting, arming), or revive a dead one for the watchman. Use only when the builder asks for `start <spec>` or the watchman's scheduled task sends `start revive <owner/repo>`; never on your own judgement.
argument-hint: <spec issue number> | revive <owner/repo>
---

# Start

A **shift** is one unattended run over one spec's tickets, from prescan to handover. This skill has two entries:

- **`start <spec>`**, from the builder at the Mac: [Prescan](#1-prescan), [Decision sitting](#2-decision-sitting), [Arm](#3-arm), then the [Shift](#4-shift).
- **`start revive <owner/repo>`**, from the watchman: see [Revive](#revive).

Run everything from the target repo's folder; [Revive](#revive) first finds and moves to it. Two rules hold throughout:

- Scripts run only as `uv run --script "${CLAUDE_PLUGIN_ROOT}/cli/<script>" ...`, never from PATH. Each prints one JSON object: exit 0 done, 1 refused (`refused` says why), 2 lease lost (stop at once).
- Before arm, scratch files live under `.git/third-shift/` in the target, never `/tmp` or anywhere outside the repo: the shift's guard refuses those paths, and nothing under `.git/` is committed. Create the folder with `mkdir -p .git/third-shift` if it is missing. After arm, no Claude tool writes scratch files at all: see [loop.md](references/loop.md)'s no-scratch-files rule.

## 1. Prescan

Input: one argument, the spec's issue number. Nothing else is taken: no ticket subset, no mode, no ceiling.

Run [references/prescan.md](references/prescan.md).

Done when `.git/third-shift/prescan.json` exists, every failed check has stopped the start (bar mains power, which only rules out away mode), and the prescan brief has reported.

## 2. Decision sitting

The only time the builder is needed. Ask with `AskUserQuestion`, the recommended option first and marked as such, up to four questions per call, until all of these are answered:

1. **Every gap**, recommendation first:
   - each decision gap from the prescan brief;
   - each string in prescan.json's `questions` (it starts with its ticket number). Arm never reads `questions`, so each one must become a gap here or it is lost. A ticket without a triage label becomes a class question. A `## Blocked by` entry with no native link, a cycle, or a ticket without criteria is answered either "fix it on GitHub, then rerun the prescan" (prescan.json is what arm freezes) or with a ruling recorded as the answer (for example "no edge: the body entry is stale", or class the ticket human);
   - each class the brief was unsure of.
2. **Mode**: day (threshold 90%) or away (98%). If prescan.json's `mains power` check failed, away is not on offer until the builder plugs in and the prescan is rerun.
3. **Away only**: one confirmation that the lid stays open, keep-awake is on, and Connect new sessions to Remote Control is on. Not confirmed means day mode or no shift; ask which.
4. **Weekly ceiling**: keep 80% (recommended), raise it to a figure for this shift, or waive it for this shift.
5. **End state**: leave the work on `third-shift/<spec-slug>` (recommended), or fast-forward the default branch to it and push.

Then write `.git/third-shift/sitting.json` in the shape `cli/shift` documents:

```json
{"classes": {"<ticket>": "agent" | "human-verified" | "human"},
 "gaps": [{"question": "...", "answer": "...", "adr": "docs/adr/NNNN-<slug>.md" | null}],
 "end_state": "branch" | "fast-forward",
 "binding_sources": ["in precedence order"],
 "warnings": ["anything the builder saw that prescan.json's warnings do not hold"]}
```

- `classes`: every ticket the brief classed or the builder settled. A class here overrides the triage label; every ticket, closed ones included, must end up with one.
- `gaps`: one entry per gap above, its `answer` in the builder's words. A decision gap gets the path of the ADR that will record it (numbered after the target's last ADR, in the target's ADR format per `docs/agents/domain.md`); a prescan question settled by a class, a ruling or a rerun gets `null`.
- `binding_sources`: the list the prescan collected, with the new ADRs added first.

Done when every gap has an answer, mode, ceiling and end state are explicit, and sitting.json is written.

## 3. Arm

Arming hands this session the lease, and from the first hook after it every permission prompt is refused. So the ADRs and the watchman are made first: after arm, only the commands in `cli/rules.json`'s allow list run (the state script, read-only git, `git add`, `git commit`, `git push origin third-shift/*`, `gh issue` reads and writes, `verify/checks`, Playwright runs, and the target's test and launch commands that setup added), and everything else is refused.

1. Write one ADR per decision gap at the path sitting.json gives it: the question, the options, the builder's answer and why, in the target's ADR format. Leave them uncommitted: they carry over onto the shift branch.
2. Create the watchman with the desktop app's scheduled tasks (`create_scheduled_task`): `taskId` `third-shift-<owner>-<repo>` (lower case), `cronExpression` `*/15 * * * *`, `prompt` exactly `/third-shift:start revive <owner/repo>`, `description` `Revives the third-shift shift on <owner/repo> if it has died`, `notifyOnCompletion` false. If the id is refused as in use, a previous shift's watchman was never removed: update that task to this schedule and prompt instead of creating a second. Keep the task id the result gives, which may differ from the one asked for.
3. Arm the shift with that task id. Pass `--ceiling <N>` to raise the ceiling, `--ceiling none` to waive it, and nothing to keep 80%:

   ```
   uv run --script "${CLAUDE_PLUGIN_ROOT}/cli/shift" arm --prescan .git/third-shift/prescan.json --sitting .git/third-shift/sitting.json --mode <day|away> --watchman <task id> [--ceiling <N|none>]
   ```

   Arm checks the hand-off, creates `third-shift/<spec-slug>` from the base commit, commits and pushes the ledger's opening entry, and arms runtime state with the watchman's task id. It answers `{"ok": true, "gen": 1, "branch", "ledger"}`; keep `gen` and `branch` for the shift.

   **On a refusal**, delete the new ADR files and the watchman's scheduled task, show the builder the `refused` text with its pointer, and stop: the shift does not begin, and nothing below runs.
   - a failed check: the check's detail names `/third-shift:setup`;
   - the base commit has moved: rerun the prescan and the sitting;
   - a gap unanswered, a ticket unclassed: back to the sitting;
   - a shift already armed for this repo: one armed shift per repo; it must end first.
4. Commit the ADRs on the shift branch and push:

   ```
   git add docs/adr/<each new ADR>
   git commit -m "#<spec>: decision sitting ADRs"
   git push origin third-shift/<spec-slug>
   ```

Done when arm answered ok, the ADRs are pushed on the shift branch, and the watchman is scheduled with its id in runtime state; or when a refusal has been shown and the ADR files and watchman are deleted.

## 4. Shift

Unattended from here: the builder answers only through Remote Control, and only the shift's own commands run. With the `gen` and `branch` arm (or revive) returned, run [references/loop.md](references/loop.md): `next`, `admit`, then for each ticket a fresh implementer, a separate reviewer, up to three fix rounds and a separate verifier, each step gated on usage and recorded with `step`; one `#<n>: <title>` commit per closed ticket and `done` with its criteria table; blockers to Needs you; `wait` when only Needs you or Stalled tickets are left.

Done when the loop reaches the [Handover](#handover), or a command exits 2 (the lease is lost: stop at once).

## Revive

`start revive <owner/repo>` comes only from the watchman's scheduled task, every 15 minutes, with nobody at the Mac. It skips the prescan, the sitting and setup: the ledger and runtime state hold everything the shift started from. A revived session has no Remote Control, so it never asks a question: [loop.md](references/loop.md) sends what needs the builder to Needs you with a notification and carries on, and its Waiting step hands over instead of asking.

1. **Is it dead?** The task cannot choose its working folder, so ask by name, from wherever this session started:

   ```
   uv run --script "${CLAUDE_PLUGIN_ROOT}/cli/shift" is-dead <owner/repo>
   ```

   `dead: false`, or any refusal: end the turn at once, with no notification and nothing else run. This is the usual answer, every 15 minutes, while a shift is alive.
2. **Be in the target.** `git rev-parse --show-toplevel` must print the answer's `target`. If it does not (or fails), move the session there with `change_directory` (`path` the `target`; setup's allow list carries `mcp__ccd_directory__change_directory`, so the move should not wait on a trust prompt with nobody there, though whether that rule suppresses the prompt is unverified live), then schedule this skill to continue with a one-off `CronCreate`: `cron` the answer's `continue_cron`, `recurring: false`, `prompt` `/third-shift:start revive <owner/repo> moved`. End the turn; the move takes effect when it ends. If the argument already says `moved` and this session is still not in the target, end the turn without trying again: the next watchman run will.
3. **Revive.**

   ```
   uv run --script "${CLAUDE_PLUGIN_ROOT}/cli/shift" revive
   ```

   With a STOP file it revives nothing: it ends the shift and answers `shift_state: "ended"`, `stop_file: true`; go to [Handover](#handover), already ended, reason `stop file`, with no revival notification. Otherwise it raises the lease, sets uncommitted work aside on `set_aside` (a pushed ref), restarts the ticket in progress from its last commit (two crashes on one ticket send it to Needs you) and returns the shift to running. Exit 1: another run revived it first, or it came back to life; end the turn quietly. Keep `gen`.
4. **Notify**, with `PushNotification` (`status: "proactive"`), one message:

   `third-shift <owner/repo>: revived as generation <gen> in a new session started by the scheduled task <watchman>; set aside: #<ticket> on <set_aside>`

   With no ticket in progress write `set aside: nothing in progress`; with a ticket but no `set_aside`, `#<ticket> restarted, nothing uncommitted`. If `ticket_state` is `Needs you`, add `; #<ticket> needs you after two crashes`.
5. **Carry on**:
   - `shift_state: "ended"` (the third revival ended it): [Handover](#handover), already ended, reason `three revivals`.
   - Otherwise: the [Shift](#4-shift) with this `gen`, marked as a revived session. `<branch>` is `third-shift/<spec-slug>`, `<repo>` this skill's argument; the ledger is `docs/third-shift-ledger/<spec-slug>.json`, the one file there whose name has no further suffix.

Done when the turn ended quietly on a live shift, the session moved and scheduled its continuation, or the revival is notified and the loop or the handover has begun, or a stop file sent it straight to the handover.

## Handover

Reached from the loop (`end` from the gate, a frontier left empty, an unhandled refusal with nothing in progress), from [Revive](#revive), or when the Stop hook says the shift has ended (three stalled tickets in a row, or a stop file). It carries a `<reason>`: the gate's `reason`, the loop's, `stop file`, or `three revivals`.

A shift that the state script has **already ended** (revive answered `shift_state: "ended"`, or the Stop hook said so) has its handover written without findings or candidates: skip to step 4, with the watchman id from revive's answer, or the one the Stop hook's reason names. Neither names one: nothing to remove.

The shift is still armed through step 3, so the allow list still binds: no file is written, and any command security-preflight tries outside the allow list is refused, which it reports as unchecked.

1. **Security findings.** Run the `dempsey-skills:security-preflight` skill over the shift's work: the diff from the ledger's opening `base_commit` to `HEAD` on the shift branch. Ask it to read, not change, and to write no report file. If that skill is not installed (no `dempsey-skills` plugin), skip it: the findings are the one line `security-preflight not installed`. Take its findings as one line each, severity first, for example `high: SQL built from the query string in src/search.ts`. None found is an empty list.
2. **ADR candidates**, the model's view and the only part of the handover the model writes: from the ledger's `notes` of kind `decision`, the ones hard to reverse that the builder should record as an ADR, one line each, `#<ticket>: <decision>; <why it deserves an ADR>`. None is an empty list.
3. **End**, with both lists as one-line JSON arrays of strings in single quotes, as `done` takes its rows (a `'` inside is written `'\''`):

   ```
   uv run --script "${CLAUDE_PLUGIN_ROOT}/cli/shift" end --gen <gen> --reason "<reason>" --findings '["high: ..."]' --candidates '["#12: ..."]'
   ```

   It writes the handover beside the ledger from the records, commits and pushes it, applies the sitting's end state (the branch alone, or a fast-forward of the default branch), redraws the status comment as the handover, removes a STOP file, and disarms. Keep its `watchman`.
   - Exit 2: the lease is lost. Stop at once, with nothing else.
   - Exit 1: the shift is still armed. Send the end notification with `end refused: <refused>` as the reason, leave the watchman (it revives the shift, and the third revival ends it), and stop.
4. **Remove the watchman**: `delete_scheduled_task` with `taskId` the `watchman` id. None recorded: nothing to remove. If the delete fails, say so in the notification: `; remove the scheduled task <id> by hand`.
5. **Notify**, with `PushNotification` (`status: "proactive"`): `third-shift <owner/repo>: shift ended: <reason>; handover on #<spec>`.
6. End the turn. The Stop hook lets an ended shift stop.

Done when `end` answered `shift_state: "ended"` (or the shift was already ended), the watchman is deleted or its failure notified, and the end notification is sent.
