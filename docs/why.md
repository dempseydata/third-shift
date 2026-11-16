# Why third-shift was built

<!-- Moved out of the README so the README can lead with purpose. This is the record. -->

## The problem
Who experiences it, what they do about it today, and what that workaround costs them.
(The six forcing questions are the front door; their answers
belong in `ideation/framing.md`, and the verdict belongs here.)

## Who reads this repo
Answered at ideation, not at ship: the repo is public — what does a reader get from the
record, and what must therefore never be in it? See `## Visibility` in `CLAUDE.md`.

## How it was built
The phases as they ran, one paragraph each, with links into `ideation/`, `definition/`,
`design/` and `docs/adr/`. Reversals told plainly — the record is the point.

- **Parallelism reversed before charting (2026-11-16).** The research settled on 2 tickets in
  parallel. While charting the map it was cut to serial for version 1. On a subscription the
  binding limit is usage per 5-hour window, not wall-clock time, so a second agent uses up the
  window faster without clearly finishing more work. Parallel worktrees were also the riskiest
  piece. The serial flow comes first; parallel work is a later map.
