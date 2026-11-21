# The state script is `cli/shift`, speaking JSON with three exit codes

The state script is a single file, `cli/shift`, a PEP 723 script with its dependencies inline, run as `uv run --script "${CLAUDE_PLUGIN_ROOT}/cli/shift" <command>`. Hooks, skills and the user-settings allow list all name it this way. Every command prints one JSON object on stdout and exits 0 when it did what was asked, 1 when the move was refused, and 2 when the lease is lost and the session must stop.

The command that arms a shift is `arm`, not `start`, so the script never shares a command name with the `start` skill; `revive` keeps its name because it is the same act at both layers. The usage gate at a step boundary is answered by `step --begin`, which takes the readings and returns proceed, pause-until, retry or end; there is no separate query command, keeping the rule that the script holds state changes only. `done --comment <file>` reads a JSON list, `[{criterion, verdict, evidence_url}]`, with `verdict` one of `met`, `not met`, `needs your run`; the script renders the comment's table itself.

We considered a `cli/state.py` with a root `pyproject.toml` (rejected: two files to keep in step for one script) and free-text output (rejected: skills and hooks would each parse prose). We considered a markdown table for `done`, and rejected it as fragile to parse.

## Consequences

- The allow rules in user settings name `cli/shift`; renaming it means rewriting settings on every machine.
- The eval set's verifier case grades the same three verdict strings.
