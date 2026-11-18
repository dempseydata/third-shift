# third-shift

An unattended software factory for Claude Code: it works a spec's tickets while the builder is
away, verifies each one, and leaves a handover.

## The shift

**Shift**:
One unattended run over one spec's tickets, from prescan to handover.
_Avoid_: night shift, run, job

**Prescan**:
The checks made before a shift starts, which settle whether each ticket carries enough to build from.

**Decision sitting**:
The one session in which the builder answers every gap the prescan found, before the shift starts.

**Frontier**:
The tickets a shift may start next: open, unblocked, and not human work.

**Admission**:
The moment the shift starts work on a ticket.
_Avoid_: dispatch, pickup

**Blocker**:
A question or limit that stops one ticket until the builder answers it; the shift carries on with the rest.

**Ledger**:
The shift's running record of each ticket's status, decisions, owed findings and nits.

**Handover**:
The report a shift leaves for the builder when it ends.

## Usage

**Usage gate**:
The check, made before work proceeds, of plan usage against the 5-hour threshold for the time of day, with the weekly limit able to veto.
_Avoid_: throttle (reserved for a possible skill name)

**Pause**:
A shift holding all admissions until the 5-hour window resets.

**Resume**:
The same session continuing its shift after a pause.

**Revival**:
A new session taking over a shift whose session died, from its ledger.
_Avoid_: restart, respawn

**Stall**:
A shift that keeps stopping without progress; it waits for the builder.

## Verification

**Checks script**:
The model-free gate the target project supplies and owns.

**Verify recipe**:
The target project's procedure for launching, driving, capturing evidence from and cleaning up its app.

**Evidence**:
A file written during this shift that a verification claim cites.
