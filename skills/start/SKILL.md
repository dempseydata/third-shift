---
name: start
description: Start a third-shift shift on a spec's sub-issues (prescan, decision sitting, arming), or revive a dead one for the watchman. Use only when the builder asks for `start <spec>` or the watchman's scheduled task sends `start revive <owner/repo>`; never on your own judgement.
argument-hint: <spec issue number> | revive <owner/repo>
---

# Start

A **shift** is one unattended run over one spec's tickets, from prescan to handover. This skill has two entries:

- **`start <spec>`**, from the builder at the Mac: [Prescan](#1-prescan), [Decision sitting](#2-decision-sitting), [Arm](#3-arm), then the [Shift](#4-shift).
- **`start revive <owner/repo>`**, from the watchman: see [Revive](#revive).

Run everything from the target repo's folder. Two rules hold throughout:

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

Written by ticket #38: `start revive <owner/repo>` (`is-dead` first, then `revive`, then the [Shift](#4-shift)). Until it is, stop and say that revival is not built yet.

## Handover

Written by ticket #38: `end` with the security-preflight findings and the ADR candidates, the watchman's removal and the end notification. Until it is, run `uv run --script "${CLAUDE_PLUGIN_ROOT}/cli/shift" end --gen <gen> --reason "<reason>"`, send one push notification `third-shift <owner/repo>: shift ended: <reason>`, and stop.
