---
name: setup
description: Prepare this Mac for unattended third-shift shifts — allow list, deny rules and the outside-write block in user settings, the gh project scope, uv, the Mac checklist and the default model — showing each edit before making it. Safe to rerun whenever the prescan names it.
disable-model-invocation: true
---

# Setup

Makes every machine-level change an unattended shift needs, in one attended sitting. Run it once per Mac, and again whenever a prescan check's detail says `run /third-shift:setup`.

Two rules hold throughout:

- **Show, then do.** Before any change, show the builder exactly what will change and ask with `AskUserQuestion`. A declined change is skipped and named in the summary; nothing else is changed in its place.
- **Safe to repeat.** Every step checks first and skips what is already in place, saying so. A rerun on a ready Mac changes nothing.

Work through the steps in order. A refusal stops setup at that step: nothing after it runs.

## 1. Mac checklist

The Mac must stay awake and reachable overnight. Check what can be read; ask about the rest.

1. **Mains power**: run `pmset -g batt`. `'AC Power'` means plugged in. If not, say a day shift may run the battery flat and away mode will be refused until it is plugged in; carry on.
2. Ask the builder to confirm, in one `AskUserQuestion` call, each of:
   - **Lid open** overnight (or closed only with an external display, keyboard and mouse attached): a closed lid sleeps the Mac, and a sleeping Mac does no work.
   - **Keep computer awake** is on: Claude desktop > Settings > Desktop app.
   - **Connect new sessions to Remote Control** is on, in Claude desktop's Settings.
   - **Prevent automatic sleeping on power adapter when the display is off** is on: macOS System Settings > Battery > Options.
   - **No OS or app update installs overnight**: a restart ends the session.
3. **Refuse** if Connect new sessions to Remote Control is off or unconfirmed: a shift's session must be reachable from the builder's phone, and a revived session must connect by itself. Say: "Turn on Connect new sessions to Remote Control in Claude desktop's Settings, then run `/third-shift:setup` again." Stop.
4. Lid, keep-awake, sleep on power adapter or overnight updates not confirmed: advise that away mode needs all four, and carry on (the decision sitting asks again before an away shift).

## 2. uv

Run `uv --version`. The plugin's scripts run only through `uv`, so if it fails, **refuse**: "Install uv (https://docs.astral.sh/uv/getting-started/installation/), then run `/third-shift:setup` again." Stop.

## 3. Allow list and deny rules

The rules live in the plugin's `cli/rules.json`, the one source the prescan also checks against (ADR 0006). They include `Skill(third-shift:start)` and `Skill(third-shift:start *)`, so a revived shift does not stall on a question about running its skill, and `git push origin third-shift/*`, the only push a shift makes. They also set `permissions.blockWritesOutsideWorkingDirectories` to `true` (Claude Code v2.1.314 or later), so `Write` and `Edit` refuse paths outside the working directories in every permission mode. It is a user setting, so it **also applies to every attended session** on this Mac, not only to shifts: say so plainly when asking.

1. See what is missing; this changes nothing:

   ```
   uv run --script "${CLAUDE_PLUGIN_ROOT}/cli/settings"
   ```

   It answers `{"ok": true, "settings": <file>, "add": {"allow": [..], "deny": [..], "set": {key: value}}, "written": false}`, or `{"ok": false, "refused": why}`: show the refusal and stop, since user settings that cannot be read are never replaced.
2. `add` empty (both lists and `set`): say the rules are already in place and go to step 4.
3. Otherwise show the builder the settings file and every rule in `add`, under "allow" and "deny", and every key in `set` with the value the settings file holds now (if any) and the value it will get, and ask to make the change. On yes:

   ```
   uv run --script "${CLAUDE_PLUGIN_ROOT}/cli/settings" --write
   ```

   It adds only the missing rules, at the end of each list, sets the `set` keys, and keeps every other setting. Report `written`.

## 4. The guard

Read `enabledPlugins` in the settings file step 3 named. The guard hooks load only when the plugin is installed and enabled through the plugin route: a key `third-shift@<marketplace>` set to `true`. If there is none, say the prescan will fail its `guard hooks` check until the plugin is installed with `claude plugin install` and enabled; a development symlink in `~/.claude/skills/` loads no hooks. Change nothing.

## 5. GitHub scopes

A shift moves cards on a Projects board, which needs the `project` scope, and pushes and writes to the tracker, which needs `repo`.

1. Run `gh auth status --json hosts --active --hostname github.com` and read the active account's `scopes`.
2. `project` present: say so and skip to step 3.
3. Otherwise show the command and ask the builder to run it themselves in this session, since it waits for a browser sign-in:

   ```
   ! gh auth refresh -h github.com -s project
   ```

   When they say it is done, read the scopes again and report them.
4. `repo` missing: say the shift cannot push or write to the tracker, and that `gh auth login` with the `repo` scope fixes it. Change nothing.

## 6. Default model

Read `model` in the settings file. The roles assume Opus, and a revived shift starts on the app's default model. If `model` does not name Opus, advise setting Claude desktop's default model to Opus (and `model` in user settings, which the prescan reads; otherwise it warns on every shift). Advise only: change nothing.

## Summary

End with one line per step: in place already, changed, declined, or advised, and anything the builder still has to do before a shift.
