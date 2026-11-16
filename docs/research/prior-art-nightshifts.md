# Prior art: marcus/nightshift and orwa-mahmoud/nightshift

Research for issue #2 on the version 1 map (#1), run 2026-11-16. Both projects were read from
their public source and docs on GitHub; neither was installed or run. Compared against
`docs/ideation/factory-research.md` and `skills/start/`.

Versions read: `marcus/nightshift` default branch, latest release v0.3.4, last commit
2026-08-20 (Go, MIT). `orwa-mahmoud/nightshift` default branch, latest release v0.36.0, pushed
2026-11-16 (shell plugin for Claude Code, Codex and Cursor, MIT).

## Answer in brief

Neither project does what third-shift version 1 must: start from `to-tickets` output on GitHub
Issues, pause *before* the 5-hour window runs out, and prove each acceptance criterion with
evidence from a verifier that did not write the code.

- **marcus/nightshift** is a scheduled "spend leftover budget" tool. It invents its own chores
  (lint fixes, dead code, doc drift) and opens a PR per chore. Its budget logic is weekly and
  decided once per run; it does not watch the 5-hour window. Borrow little: the reserve idea and
  provenance stamped on each output.
- **orwa-mahmoud/nightshift** is the close cousin: a Claude Code plugin for long, unattended,
  accountable shifts over an agreed list. Borrow a lot: the on-disk contract, the Stop-hook gate,
  the outside watchman for crashes, per-item token measurement from the host's own records, the
  evidence catalog, the "park with a default" rule, and the one-page morning receipt. It too
  handles usage limits only *after* they are hit.

## 1. marcus/nightshift

### What it is

A Go command-line tool run by cron, launchd or systemd that "uses your leftover Claude / Codex
budget" overnight to find and fix codebase chores, landing each as a branch or PR
([README](https://github.com/marcus/nightshift/blob/main/README.md)). It picks from 20+ built-in
task types, scored by priority and staleness, with per-task cooldowns
(`internal/tasks/selector.go`, `internal/state/state.go`). It does not read a ticket tracker for
work; GitHub is an output.

### Pacing usage limits

- Budget is a share of the **weekly** allowance. Daily mode allows `max_percent` (default 75%)
  of `weekly / 7`; weekly mode spreads what remains over the days left, optionally more
  aggressively near week end. A `reserve_percent` (default 5%) is always held back for the
  owner's daytime work (`internal/budget/budget.go` `calculateDailyAllowance`,
  `calculateWeeklyAllowance`, `applyReserve`; [budget docs](https://github.com/marcus/nightshift/blob/main/website/docs/budget.md)).
- "Used percent" comes from local token counts in Claude Code's `stats-cache.json`, falling back
  to session JSONL files (`internal/providers/claude.go`). The weekly total is inferred by
  scraping `/usage` in a hidden tmux session and dividing local tokens by the scraped percentage
  (`internal/tmux/scraper.go`; formula in the budget docs).
- The check happens **once per project at planning time**: `selectProvider` computes an
  allowance, and tasks whose cost tier fits are selected (`cmd/nightshift/commands/run.go`).
  There is no check between steps.
- The 5-hour session's reset time is scraped but used only for display in `nightshift budget`
  (`cmd/nightshift/commands/budget.go`); no gate reads it.

### Resuming after a stop

There is no resume. Each run is a fresh, short process; a task that fails or exhausts its three
review iterations is marked failed or abandoned (`internal/orchestrator/orchestrator.go`,
`DefaultMaxIterations = 3`). State in SQLite only records what ran, so the next night's run picks
other work, and stale "assigned" markers are cleared by age (`ClearStaleAssignments`).

### Proving work was done

A plan → implement → review loop, each step a separate agent call, up to three rounds. The review
returns JSON with `passed`; if the JSON cannot be parsed, pass/fail is inferred from keywords such
as "lgtm" or "bug" in the text (`inferReviewPassed`). No tests are required to run, and no
evidence files are produced. Each PR body carries a hidden metadata block: task, provider, cost
tier, branch, iterations, duration, run start (`buildMetadataBlock`).

### Reporting to an absent builder

A Markdown run report per run and an optional daily "morning summary": duration, budget at start,
used and remaining, and tasks completed, failed and skipped with reasons
(`internal/reporting/run_report.go`; [run lifecycle](https://github.com/marcus/nightshift/blob/main/docs/guides/run-lifecycle.md)).
Files land in the user's local data folder; nothing is pushed to a phone.

## 2. orwa-mahmoud/nightshift

### What it is

A native plugin for Claude Code, Codex and Cursor that keeps an agent working through an agreed
**punch list** while the owner is away, then leaves receipts
([README](https://github.com/orwa-mahmoud/nightshift/blob/main/README.md),
[why it exists](https://github.com/orwa-mahmoud/nightshift/blob/main/docs/why-nightshift.md)).
Work comes from a planning conversation (the "plan room"), from 32 ready-made shifts, or from
GitHub issues copied in read-only (`runtime/import-issues.sh`: "Never mutates GitHub"). Its
runtime is deterministic shell and awk scripts, not the model.

### Pacing usage limits

- **Reactive only.** No threshold or reserve exists. When a Claude session stops on a usage
  limit, the outside watchman treats it like an API error: it retries, and when the transcript's
  last host-marked error names a rate or usage limit, it doubles its wait between attempts up to
  an hour (`runtime/claude/watchman.sh`, header and `usage_limited_tail`). On Codex it waits for
  the reset time Codex reports. `watchAfterUsageLimit: false` makes it stand by for the owner
  instead ([knobs](https://github.com/orwa-mahmoud/nightshift/blob/main/docs/knobs.md)).
- **Per-item budgets** cap a single item, not the account: a soft and a hard limit in working
  time and/or tokens. Soft tells the agent to finish; hard allows only committing work in
  progress and writing the receipt ([item budgets](https://github.com/orwa-mahmoud/nightshift/blob/main/docs/item-budgets.md)).
  Limits are proposed from past receipts.
- **Measured usage.** Token use per item is read by hooks from the session transcript the host
  writes, deduplicated by request id, as a cumulative counter with start and tick marks; no
  estimate, no network (`lib/usage.sh`, `lib/usage-claude.awk`). Paused time is split by reason,
  including "usage limit" (`lib/usage-pauses.awk`).

### Resuming after a stop

The strongest part of either project.

- The contract lives on disk (`.nightshift/punch-list.md`), so it survives compaction, new
  sessions and even a switch to a different agent host
  ([vocabulary](https://github.com/orwa-mahmoud/nightshift/blob/main/docs/vocabulary.md)).
- A **Stop hook "clock-out gate"** blocks the agent from ending while the armed list has open
  items, and re-injects the contract. It releases only on a stop-work file, an empty list, or a
  deadline. Repeated stops with no progress (no tick, no commit) are logged as a stall and held
  for the owner by default (`hooks/clock-out-gate.sh`).
- A **watchman outside the session**, woken every ten minutes by default, revives a dead or
  wedged session: `claude --resume <id>`, then `--continue`, then a fresh `claude -p`. It acts
  only on positive evidence of death (process gone, API-error tail, host roster without the
  session) and stands down on any sign of life or of the owner pressing Escape.
  ([How it works: recovery](https://github.com/orwa-mahmoud/nightshift/blob/main/docs/how-it-works.md#recovery)).
- A **process lease** with a generation number stops an old, stale session from acting once a
  revived one has taken over.
- Known limit: a headless revival writes to the conversation, but an already-open app panel does
  not refresh; the owner must reopen the thread to see it (same section).

### Proving work was done

- Each item carries `Verify:` lines (WHEN/THEN statements and commands) and optional `Evidence:`
  lines. "`Verify:` is what must pass. `Evidence:` is what you look at."
  ([evidence](https://github.com/orwa-mahmoud/nightshift/blob/main/docs/evidence.md)).
- An **evidence catalog** of ten entries says what to capture per kind of change (UI screenshots
  at named widths, API request and schema diff, performance before/after with run counts, and so
  on), and the owner can add entries.
- A named evidence file can be set to `off`, `report` or `block`; `block` keeps the item open,
  and the gate will not clock out, until the file exists.
- Project verification commands run at a chosen cadence (per item, final, none). The morning
  receipt never reports a check that did not run as passed, and "the agent's own claim about its
  work never counts as proof"
  ([morning receipt](https://github.com/orwa-mahmoud/nightshift/blob/main/docs/morning-receipt.md)).
- The same agent writes and checks its work; there is no separate verifier.

### Reporting to an absent builder

- One **receipt per item**: delivered, tried and rejected, checks run, checks that could not run,
  evidence, working time and tokens by session.
- A **morning receipt** written once at clock-out from the records alone: how it ended, time and
  tokens with paused time by reason, items, the three largest changes to review first,
  interruptions, decisions waiting, found-but-not-fixed, and next step. Missing records read
  `absent` rather than being guessed.
- **Questions are parked, not asked.** During a shift `AskUserQuestion` is denied by a hook; the
  agent records the decision with the default it chose and how to roll it back in
  `parking-lot.md` and carries on (how-it-works, "Questions, stalls, and deadlines").
- An optional one-line notification at shift end (`notifyCommand`). No board; progress is files
  plus `/nightshift:status`.

## 3. Against third-shift

| Concern | marcus | orwa-mahmoud | third-shift today / planned |
| --- | --- | --- | --- |
| Where work comes from | Its own chore catalogue | Agreed punch list, plan room, read-only issue import | `to-tickets` tickets on GitHub; never re-plans |
| Usage pacing | Weekly share, checked once per run, 5% reserve | None; waits out a hit limit | Gate at every step boundary on the 5-hour figure; day/away threshold; weekly veto |
| Resume | None | Disk contract, Stop-hook gate, outside watchman, lease | Ledger on the branch (planned pause); crash resume not yet specified |
| Proof | Reviewer verdict, keyword fallback | Verify lines, evidence catalog, block-on-missing-file; same agent | Separate verifier subagent, evidence per acceptance criterion |
| Questions | n/a | Parked with a default; ask tool denied | Blockers notify and park; decision sitting up front |
| Report | Run report file | Item receipts plus morning receipt | Handover report, push notification, Projects board, Remote Control |
| Tracker writes | Opens PRs | Never writes to GitHub | Comments, labels, board cards through the state script |

## 4. What to borrow

From **orwa-mahmoud/nightshift** (MIT):

1. **A Stop-hook gate over the ledger.** While a shift is armed and the frontier is not empty,
   the session may not end; the hook re-injects the shift's next step. Release on: frontier
   empty, a stop file, the usage gate's planned pause, or the weekly veto. Count stops with no
   progress as a stall and hold for the builder.
2. **Measure tokens per ticket from the transcript**, deduplicated by request id, from hooks.
   This is the burn-rate-per-ticket figure `factory-research.md` lists as unknown and the ledger
   must record. It does not give the plan-usage percentage; the usage gate still needs that.
3. **An outside watchman for interrupted resume**, as the answer to the "Interrupted resume" fog:
   it revives only on positive evidence of death, tries resume-by-id first, and stands down for a
   planned pause, a stop file or a finished shift. A lease (or simply the ledger's owner field)
   keeps a stale session from acting. Note the panel-refresh limit for Remote Control users.
4. **The evidence catalog idea**, per kind of change, with `block` meaning a ticket cannot close
   until its named evidence file exists. This fits the verify recipe and gives the verifier
   subagent a checklist per acceptance criterion.
5. **A morning page built only from records**: never call an unrun check passed; say `absent`
   when a record is missing; list paused time by reason; name the largest changes to review
   first.
6. **Park reversible decisions with a default and a rollback note** rather than stopping. The
   existing night shift already notifies and parks blocked tickets; the narrower borrowing is
   recording the default chosen for small, reversible calls.
7. **Item budgets** (soft then hard, time and tokens) as a per-ticket stop-loss, sized from past
   ledgers once there are some.

From **marcus/nightshift** (MIT):

8. **A reserve held back for the builder's own work**, which the away (98%) and day (90%)
   thresholds already express; nothing new to add beyond confirming the defaults.
9. **Provenance stamped on each output**: a hidden metadata block (ticket, model, rounds,
   duration, tokens) in each resolution comment, so the board and later tooling can read it.

## 5. What not to borrow

- marcus's **tmux scrape of `/usage`** and its token-to-percentage calibration. The settled
  design reads plan usage from the desktop app's usage tool; scraping is fragile and Claude Code
  only.
- marcus's **keyword fallback for review verdicts**. A pass must come from structured output or
  evidence, never from words like "lgtm".
- orwa-mahmoud's **reactive limit handling** as the main mechanism. Waiting out a hit limit is
  the fallback for a crash, not the plan; third-shift pauses before the limit.
- orwa-mahmoud's **plan room and ready-made shifts**. Planning belongs to `to-spec` and
  `to-tickets`; the factory never re-plans.
- orwa-mahmoud's **multi-host support** (Codex, Cursor, Windows PowerShell). Version 1 is Claude
  Code on a subscription.
- **Self-verification** in both. third-shift keeps the author and the verifier separate.

## 6. What makes third-shift different

- **Input:** tickets already written and linked by `to-tickets`, with blocking edges; neither
  project reads a ticket graph. orwa-mahmoud imports issues read-only and rewrites them into its
  own list.
- **Proactive pacing on the 5-hour window**, checked at every step boundary, with a per-shift
  day/away threshold and a weekly veto. marcus paces weekly and once per run; orwa-mahmoud does
  not pace.
- **An independent verifier** that writes evidence per acceptance criterion. Both prior arts let
  the doer judge its own work.
- **The tracker is the live view**: comments, labels and a GitHub Projects board written by a
  deterministic state script, watchable from a phone, with Remote Control for answers.
  orwa-mahmoud keeps everything in local files; marcus writes reports to a local folder.

## 7. Bearing on open questions on the map

- **Interrupted resume:** orwa-mahmoud's watchman is a worked design: outside the session,
  positive-evidence-only revival, resume-by-id then continue then fresh, a lease against stale
  sessions. It suggests the answer is a scheduled outside process, not anything inside the
  session.
- **State script interface:** worth adding a "stalled" state and a "paused: usage" state
  distinct from "paused: owner", so the handover can split paused time by reason.
- **Burn rate per ticket:** measurable today from transcripts via hooks, without the usage tool.
- **First eval set:** orwa-mahmoud ships fixtures for malformed contracts, unsafe authority,
  missing tools and an unsupported environment (`evals/fixtures/v1/`); a similar shape suits
  third-shift's prescan.
