# Revive a dead shift from an app scheduled task, not from the command line

A shift whose session dies (a crash, the app quitting, the Mac sleeping) is revived by a recurring Claude desktop app scheduled task. The task is armed when the shift starts and removed at handover. When it finds positive proof of death, it starts a fresh session that takes over the shift from its ledger. We considered orwa-mahmoud/nightshift's command-line watchman (`claude --resume`, then `--continue`, then `claude -p`), which can pick up the same conversation. We rejected it because a session started from the command line cannot reach the desktop app's usage tool. Our usage gate fails closed when usage is unreadable, so a shift revived that way could never do any work.

## Consequences

- Revival is tied to the desktop app. A scheduled task runs only while the app is open; a run that falls due while the app is closed or the Mac is asleep fires at the next launch or wake.
- A revived shift runs in a new session, not in the old conversation, so a Remote Control panel left open on the old session goes stale. Each revival sends a push notification that names the new session.
- The same watchman also covers a planned pause whose session dies, which is why the usage gate's one-off backstop task was dropped ([Usage gate: read plan usage at each step, pause, and resume after reset](https://github.com/dempseydata/third-shift/issues/6)).
