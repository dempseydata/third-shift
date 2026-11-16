# Factory research — input to the wayfinder map

Research run 2026-11-16, before any design. It compares four public "agentic software factory"
implementations against the requirements below, and records the decisions and unknowns that
came out of it. Everything external was read from source and docs; nothing was installed or run,
and none of the companion videos' transcripts could be obtained.

## Requirements

1. Ideation and requirements stay with Matt Pocock's skills (`wayfinder`, `to-spec`,
   `to-tickets`). The factory starts after `to-tickets` and does not re-plan.
2. Before building, verify each ticket carries enough to build from.
3. Automatic verification, so manual QA shrinks.
4. Observability through an asset viewable from a phone or a second machine, with a way to
   give input when asked. A kanban board is the preferred shape.
5. Controlled parallelism, changeable while the factory runs.
6. Pause before the 5-hour usage window is exhausted (about 90–95% by day, 98% overnight),
   resume shortly after reset.
7. Runs in Claude Code on a subscription, not the API.

## What was compared

| Requirement | zazencodes software-factory v2 | Cole Medin's factory on Archon | Cursor pstack | The existing night shift |
| --- | --- | --- | --- | --- |
| Starts after `to-tickets` | No: always runs its own intake and spec-writer; ignores blocking edges | No: mandatory triage, own labels, no sub-issues or native blocked-by | No: free-text prompt | Yes: reads the tracker's frontier |
| Sufficiency check | Yes, per issue | Yes, two layers | Soft only | Yes: prescan and decision sitting |
| Verification | Checks script, risk-routed reviewers | App check with evidence files, merge gate | Strongest ideas, not a product | Suite, reviewer, probes; no real-app check |
| Phone-visible progress | Localhost dashboard | Web console; needs a hosted server | Decision log | Ledger file, push notifications |
| Parallelism | Yes | Yes, re-read live | Yes | Serial |
| Usage-window pause | None | Reactive only, at the limit | None | None |
| Subscription | Yes | Yes | n/a | Yes |

Sources: `zazencodes/zazencodes-season-3` (`src/software-factory-claude-code-v2`),
`coleam00/ai-software-factory`, `coleam00/factory-mission-control`, `coleam00/Archon`
(v0.14.0), `cursor/plugins` (`pstack`).

## Why not build on Archon

- Its intake is the product. The queue requires its own LLM triage and labels and has no
  operations for sub-issues or native dependencies; a `ready-for-agent` ticket means nothing
  to it, and triage may route a finished ticket back to planning.
- A proactive pause needs a source patch. Archon receives usage events from Claude, logs them
  and discards them, so no workflow node can gate on a percentage.
- No board view, and phone access means hosting and securing a server.
- Browser-only verification.
- Pre-1.0, breaking changes in most releases, one dominant committer.

## What to borrow

- **zazencodes:** a small deterministic state script as the only writer of job state; a
  `checks.sh` gate the project owns; a worktree per job; routing reviewers by risk.
- **Archon (MIT):** review-lens and merge-gate prompts; concurrency re-read before every
  admission, so a change takes effect without a restart.
- **Cole Medin's factory:** every verification claim cites an evidence file written in that
  run; retry caps then hand to the human.
- **pstack:** the author never verifies their own work; a generated per-repo verify recipe
  (launch, drive, evidence, cleanup) that must prove itself once; findings count only with a
  rerunnable command; an append-only decision log.

Not borrowing: holdout scenarios (their author has since dropped them), mutation calibration,
multi-vendor review panels.

## Decisions so far

- **Base:** extend the existing night shift, in this repo, as a plugin named `third-shift`.
  Skills are named for actions (`start`, and candidates `resume`, `status`, `throttle`,
  `handover`); implementer, reviewer, fixer and verifier stay subagent briefs.
- **Intake:** `to-tickets` output. GitHub Issues is the standard tracker for factory runs;
  local `.scratch` tickets remain supported serially with the ledger only.
- **Parallelism:** 2 in the first version, never two tickets where one blocks the other.
  Burst beyond that is a later map.
- **Usage gate:** in the Claude desktop app, the orchestrator reads plan usage (5-hour and
  weekly percent used, reset times) from the app's built-in usage tool before each admission.
  The weekly limit can veto. A terminal fallback via statusline data is deferred.
- **Verification:** target-agnostic core; each project supplies a checks script and a verify
  recipe. For web: `playwright-cli` first (the verifier's test file is both the evidence and
  the regression test), those test files as the model-free gate, Playwright MCP for attended
  sessions only. `agent-browser` is not adopted: it cannot produce a repeatable test.
- **Board:** a GitHub Projects board over the tickets.
- **Observation and input:** Remote Control for the transcript and for answering questions.

## Not yet known

- How two parallel worktrees merge back cleanly, and the rule for tickets that touch the same
  files without a blocking edge between them.
- Whether the factory can move cards on a GitHub Projects board with ordinary `gh` scopes.
- Whether the built-in usage tool is reachable in a session steered through Remote Control.
- Whether statusline usage data runs in the desktop app and stays fresh through a long
  unattended run (needed only for the terminal fallback).
- What a verify recipe looks like for a native iOS app and for a Dockerized service.
- Whether Claude Code's own continue-after-reset behavior can carry the resume, given it
  fires at the limit and not at a reserve threshold.
- Burn rate per ticket, which burst needs; the ledger must start recording it.
- Hooks receive no plan-usage data (confirmed against the hooks reference), so a hook can
  enforce a pause only by reading a figure something else wrote.

## Prior art to read before charting

- `marcus/nightshift` — built around spending leftover Claude and Codex budget; the same
  idea as burst. Not yet read.
- `orwa-mahmoud/nightshift` — long-running accountable coding shifts. Not yet read.

## First proving project

Not chosen. The recommendation is a web project, because the Playwright chain verifies it end
to end; a native iOS app and a Dockerized platform follow as the second and third targets.
