# Briefs

Prompts for the shift's subagents, and the role table that sets how each is spawned. Spawn every **step** as a fresh foreground subagent (`general-purpose`), passing its role's `model` and `effort` from the table. Fill each slot (a name in braces) from `prescan.json`, the ledger and the earlier steps' reports, as listed under **Slots**.

## Role table

| Role | Model | Effort | Starting cost (guess) |
| --- | --- | --- | --- |
| Prescan | Opus | high | 5 |
| Implementer | Opus | medium | 6 |
| Reviewer | Opus | high | 5 |
| Fixer | Opus | medium (round 3: high) | 3 |
| Verifier | Sonnet | medium | 3 |

- `model` is passed as `opus` or `sonnet`. Fix round 3 is the only escalation; nothing else changes model or effort during a shift. To change a default, edit this table between shifts.
- **Starting cost** is the role's guess at one step's cost, in points of the 5-hour window. Pass it as `--guess` to `admit` and `step --begin`. The usage gate uses it only until the role has step records; after that it takes the largest of the role's last 5 recorded steps. Every figure here is a guess: no step has been measured yet. Each is set high on purpose, since a guess that is too high only pauses a shift early, and one that is too low lets a step run past 100%.

## Slots

Every slot any brief uses, in one place. A subagent cannot open files inside this skill, so paste text, never a path into the skill.

- `{ticket}`: the ticket's number and title, and how to read it (`gh issue view <n> --json title,body,comments`).
- `{n}`: the ticket's number alone.
- `{spec}`: the spec's issue number and title, and how to read it (`gh issue view <spec> --json body`).
- `{branch}`: the shift branch, `third-shift/<spec-slug>`.
- `{sources}`: the binding sources, in precedence order: ADRs, then closed decision tickets, then the spec, then everything else only where those are silent.
- `{project_rules}`: the target's rules from its `CLAUDE.md` or `AGENTS.md`: visibility, guarded paths, hooks, anything never to be committed.
- `{conventions}`: contracts settled so far: the sitting's ADRs and earlier tickets' decisions from the ledger.
- `{owed}`: the ledger's owed entries for this ticket, or "none".
- `{seams}`: the spec's test seams. Tests drive only these, never internals.
- `{test_cmd}`: the suite command, and how to run a single test file.
- `{test_cmd_ticket}`: the command that runs only this ticket's tests.
- `{criteria}`: the ticket's criteria as frozen in the ledger, numbered from 1, each as exact text.
- `{tickets}`: from `prescan.json`, each ticket's number, title, labels, native blocking edges and extracted criteria.
- `{decisions}`: the implementer's reported decisions that no source made, one per line.
- `{findings}`: the reviewer's must-fix findings, and the nits small enough to fix in the round, each with file:line.
- `{prior_fixes}`: empty on a first review. On a re-review: the fixes applied, then "Confirm each is correct and nothing regressed. Re-check the whole diff, not just the fixes."
- `{probes}`: the full text of [probes.md](probes.md).

Two rules recur in every brief that runs commands, and are written into each so a brief stands on its own: long commands run in the foreground, and a timed-out suite is a blocker naming `verify/checks`; scratch files stay under `.git/third-shift/`, because the shift's guard refuses any path outside the repo, `/tmp` included, and nothing under `.git/` is ever committed.

## Prescan

```
Read-only: edit nothing, commit nothing, write nothing to the tracker.

Scan {spec} for what would stop an unattended shift. Read the spec, every binding source in
{sources}, the target's verify recipe `verify/recipe.md`, and these tickets, which are the
spec's sub-issues and nothing else:
{tickets}

1. Decision gaps. A gap is a hard-to-reverse choice that no binding source makes, usually a
   contract: something one ticket produces that another ticket, a user, or another program
   consumes. Look for: CLI commands, arguments, flags and the tool's name (and collisions such
   as a command sharing the tool's name); machine-readable output fields and exit codes; file
   and folder layouts and names, and which paths are gitignored; file formats one ticket writes
   and another reads; config keys later tickets must follow; URL/query/DOM contracts between
   components; where a deliverable lives and how it is installed; places where binding sources
   contradict each other.

   Easy-to-reverse choices are not gaps: leave them out of the list entirely. The implementer
   makes them and records them.

2. Criteria against the recipe. For each criterion of each ticket labelled ready-for-agent,
   judge whether the verify recipe can reach it: launch the app, drive it, and capture evidence
   of the stated outcome with a model-free test. A criterion is unreachable when it needs a
   person's judgement (taste, tone, "feels"), a real outside service or account, a device or
   surface the recipe does not drive, or anything else the recipe cannot launch or observe.

Report, in this order:
- Each gap in under 80 words: the question; the producing and consuming tickets; two or three
  options with your recommendation first; why it is hard to reverse.
- Human-verified: each ticket with an unreachable criterion, quoting that criterion and saying
  in one line why the recipe cannot reach it. The shift builds these tickets and leaves them
  for the builder to verify.
- Human: each ticket whose building itself needs a person (an outside account signed up, a
  purchase, a physical device), with the reason in one line.
- Every other ready-for-agent ticket is agent; list their numbers.
```

## Implementer

```
Implement ticket {ticket} of {spec}, on the checked-out branch {branch}.

Read first: the ticket; the spec; {sources} (earlier entries win where they disagree); the
project's domain docs; the code already on the branch.

Established conventions (keep them): {conventions}
Owed to this ticket by earlier reviews (part of your scope): {owed}

Build it test-first with the `tdd` skill. Test only through
{seams}; never test internals. Smallest working change: no speculative abstractions, and
stdlib or already-installed dependencies first. Scope: this ticket's acceptance criteria and
what it owes, nothing more. Every existing test stays green: {test_cmd}.

Run long commands (the suite, `verify/checks`, a browser run) in the foreground, never in the
background; the foreground caps a command at 10 minutes. If the suite times out, stop and
report a blocker naming `verify/checks`. Keep any scratch file under `.git/third-shift/`;
the shift's guard refuses paths outside the repo, `/tmp` included.

Project rules: {project_rules}. Commit nothing, push nothing, write nothing to the tracker.

If the ticket needs a hard-to-reverse decision that no binding source makes, STOP and report
the question with your recommendation instead of building. Make easy-to-reverse choices
yourself, and record each one.

Report in under 200 words: files changed; the test command and its counts; each acceptance
criterion as met, not met, or needs your run; each owed entry as paid or not; every decision
you made that no source made, one per line, with the sources you checked.
```

## Reviewer

```
Review only: edit nothing, commit nothing, write nothing to the tracker. Do the review
yourself; if a skill you use spawns sub-agents, wait for all of them before reporting.

Review the uncommitted diff for ticket {ticket} of {spec} on branch {branch}. Read the ticket,
the spec, {sources}, and the diff.

{prior_fixes}

1. Use the `mattpocock-skills:code-review` skill against the acceptance criteria, the spec and the sources.
   Tests drive only {seams}.
2. Probe: try every applicable probe below by hand, with synthetic input. Report what you
   reproduced, not what you suspect.
   {probes}
3. Adjudicate each decision the implementer made that no source made:
   {decisions}
   For each, quote the source that settles it, or say it is unsettled and whether it is hard
   to reverse. A hard-to-reverse unsettled decision is must-fix: the shift raises it as a
   blocker.
4. Owed to this ticket by earlier reviews: {owed}. Each one left unpaid is must-fix.
5. Check the project rules: {project_rules}. Run a dry-run stage (`git add -A --dry-run`).
6. Run {test_cmd} in the foreground; record the count and duration. If it times out, report
   a blocker naming `verify/checks`. Keep any scratch file under `.git/third-shift/`.
7. Run `ponytail:ponytail-review` over the diff, if installed.

Must-fix means: an unmet acceptance criterion; a contradiction of the spec, an ADR or a
binding decision ticket; a broken standing invariant; a defect you reproduced; a test likely
to flake. A finding that a later ticket's criteria cover is owed to that ticket, not
must-fix. Everything else is a nit.

Report in under 220 words: CLEAN, or MUST-FIX with file:line and a one-line fix each; your
adjudications; owed findings as `#<later ticket>: <finding>`; nits; the test result.
```

## Fixer

```
Fix review findings in the uncommitted work for ticket {ticket} of {spec}, on branch
{branch}. Read the changed files and the ticket first.

Fix exactly these:
{findings}

Use `tdd`: write a failing test for each defect first, through {seams} only. Smallest change.
Nothing beyond the list. The ticket's tests stay green; run {test_cmd_ticket}.

Run long commands in the foreground, never in the background; the foreground caps a command
at 10 minutes. If the suite times out, stop and report a blocker naming `verify/checks`.
Keep any scratch file under `.git/third-shift/`; the guard refuses paths outside the repo.

Project rules: {project_rules}. Commit nothing, push nothing, write nothing to the tracker.

If a fix needs a hard-to-reverse decision that no source makes, STOP and report it. Record
any easy-to-reverse choice you make.

Report in under 100 words: what changed, the test counts, and any decision you made.
```

## Verifier

```
Verify ticket {ticket} of {spec} on branch {branch}. You did not write this code; your job is
evidence, not repair.

You may read anything, app code included, to learn how a term in a criterion appears in the
app. Write only under `e2e/`, `verify/evidence/` and scratch under
`.git/third-shift/` (never committed). Never edit app code, config, the
fixtures, `verify/recipe.md`, `verify/checks` or the Playwright config, even to make a test
pass. Commit nothing, push nothing, write nothing to the tracker. Project rules: {project_rules}.

The criteria, numbered:
{criteria}

Follow the target's `verify/recipe.md`, its sections in order: launch, drive the app to
explore each criterion, clean up the exploration before any model-free run, then evidence.

For each criterion k:
1. Write one test file, `e2e/{n}-<k>.spec.ts` (or the extension the recipe names).
   - Its title quotes the criterion's THEN clause.
   - One expect per thing the clause names (a count, a link, an absence), and nothing else.
   - Any data the criterion names is read from the fixture at run time, never copied into
     the test.
   - It attaches one screenshot of the described state, saved as
     `verify/evidence/{n}/<k>.png`.
2. If the recipe cannot reach the criterion (a person's judgement, an outside service, a
   surface the recipe does not drive), write no test. Write `verify/evidence/{n}/<k>-steps.md`
   instead: the steps for the builder to check it by hand.

Run the tests model-free, as the recipe's evidence section says, in the foreground, never in
the background; the foreground caps a command at 10 minutes. If the run times out, stop and
report a blocker naming `verify/checks`. Save the run's JSON report as
`verify/evidence/{n}/report.json`, then strip machine paths from it: replace the repo's
absolute path with `.` and your home directory with `~`, and search the file to confirm no
absolute path remains. Keep any scratch file under `.git/third-shift/`; the shift's guard
refuses paths outside the repo, `/tmp` included.

Verdicts, one per criterion:
- met: its test exists, passed in this run, and its screenshot is saved.
- not met: its test failed. Quote the failure. Never weaken a test to pass it.
- needs your run: the recipe cannot reach it, and its steps file is written.
Never return met for a criterion without a passing test and its evidence. A criterion with no
evidence is not met.

Report in under 200 words: the recipe steps you ran, files written, and any blocker. End with
one JSON array, one row per criterion, criterion text copied exactly:
[{"criterion": "...", "verdict": "met | not met | needs your run",
  "evidence": "<repo-relative path>#L<a>-L<b>"}]
where evidence is the criterion's test file and its line range, or its steps file. The path is repo-relative, with no leading `./` and no `.` or `..`
segments.
```
