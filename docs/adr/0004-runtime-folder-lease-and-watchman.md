# Runtime state lives in ~/.third-shift/<owner>/<repo>/, and the first hook claims the lease

Runtime state for a target lives in `~/.third-shift/<owner>/<repo>/`, outside every repo and outside the plugin cache, so it survives plugin upgrades. The builder's stop file is `STOP` in that folder.

Hooks receive a `session_id`, not the lease generation. After `arm` or `revive` sets a new generation, the first hook event records its `session_id` against that generation in runtime state; every later hook compares its own `session_id` to the recorded one. A session that does not match is not the shift's, and the hook does nothing.

The watchman's scheduled task carries the prompt `/third-shift:start revive <owner/repo>` and runs in the target's folder. The skill runs `is-dead` first and exits quietly if the shift is alive. The task id is kept in runtime state so the shift can remove the task at `end`.

We considered `${CLAUDE_PLUGIN_DATA}` and `~/Library/Application Support/third-shift/` (rejected: hard for the builder to find when making the stop file), and passing the session id to `arm` from the skill (rejected: unverified that a session can read its own id). We considered `start revive` with no argument (rejected: wrong with two targets on one Mac).
