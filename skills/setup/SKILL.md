---
name: setup
description: Prepare this Mac and this target for unattended third-shift shifts — allow list, deny rules and the outside-write block in user settings, the gh project scope, uv, the Mac checklist and the default model; then, in a web-app target, the board, the Playwright pin, and a drafted, proven and committed verify recipe and checks script — showing each change before making it. Safe to rerun whenever the prescan names it.
disable-model-invocation: true
---

# Setup

Makes every change an unattended shift needs, in one attended sitting: the machine part (steps 1–6) once per Mac, the target part (steps 7–12) once per target and once per new spec. Run it from the target's folder, and again whenever a prescan check's detail says `run /third-shift:setup`.

Two rules hold throughout:

- **Show, then do.** Before any change, show the builder exactly what will change and ask with `AskUserQuestion`. A declined change is skipped and named in the summary; nothing else is changed in its place.
- **Safe to repeat.** Every step checks first and skips what is already in place, saying so. A rerun on a ready Mac changes nothing.

Work through the steps in order. A refusal stops setup at that step: nothing after it runs. After step 6, if the working folder is not a git repository whose `origin` is on GitHub, end with the summary: there is no target to prepare.

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

## 7. The target

The target part commits to the default branch, so it starts from that branch as origin has it.

1. Run `gh repo view --json nameWithOwner,defaultBranchRef`. Refuse unless the working folder is on the default branch with a clean `git status --porcelain`: "Commit or stash your changes and check out <default branch>, then run `/third-shift:setup` again." Then `git pull --ff-only`; a failure refuses with its message.
2. **Refuse a target with no web app.** Version 1 has one verification path: a browser driving the app. Look for it: a `package.json` whose scripts build and serve pages (Next.js, Vite, Astro, Remix, SvelteKit, a server rendering HTML). A command-line tool, a library, a native app or a service with no pages refuses: "third-shift version 1 verifies web apps only, and this target has none." Stop. If unsure, ask the builder which command serves the app's pages; no answer refuses.

## 8. The board

A shift draws its cards on one board per target, `third-shift: <repo>`, with a view per spec (ADR 0006).

1. Ask which spec the next shift will work (its issue number). Show: the board is found by its title or created, linked to the repo, and given its columns, the Spec and Why fields, and a view for that spec. Ask to go ahead. On yes:

   ```
   uv run --script "${CLAUDE_PLUGIN_ROOT}/cli/shift" setup-board --spec <N>
   ```

2. `made` empty: the board was already in place. Otherwise name what was made and give the board's `url`. A refusal (usually the `project` scope) stops setup; step 5 fixes the scope.

## 9. Pin `@playwright/test`

A shift must never download a browser mid-run, so the target pins the version whose chromium is already installed on this Mac.

1. Find it; this changes nothing:

   ```
   uv run --script "${CLAUDE_PLUGIN_ROOT}/cli/recipe" pin
   ```

2. `pinned: true`: already in place. A refusal: show it and stop.
3. Otherwise show the command, with the `version` it found, and that it edits `package.json` and the lockfile, and ask. On yes run it, with the target's package manager if it has another lockfile (`pnpm add -D -E`, `yarn add -D -E`):

   ```
   npm install --save-dev --save-exact @playwright/test@<version>
   ```

   Run `pin` again: it must answer `pinned: true`, or stop with what it says.

## 10. Draft what is missing

Three pieces make a target verifiable (map #7, #16). Keep each one the target already has, unchanged; draft only what is missing, from the app as it is (read its `package.json`, routes and pages). Show each draft in full and ask to approve it; a declined draft can be redrafted with the builder's comments, but a target missing any piece cannot pass the prescan, so say so and stop if the builder declines it.

- **The Playwright config**, `playwright.config.ts` (or the target's language): tests in `e2e/`; a `webServer` that builds the app and starts it on a fixed port of its own, with `reuseExistingServer: false` so evidence never describes other code; chromium only; a JSON reporter beside the list reporter. Add a `test:e2e` script (`playwright test`) to `package.json`, and `test-results/` and `playwright-report/` to `.gitignore`, or every run dirties the tree and the prescan's clean-start check fails.
- **The checks script**, `verify/checks`, executable: `#!/bin/sh` with `set -e`, then everything the target already checks model-free (lint, type check, unit tests, whichever exist) and `npm run test:e2e`. It exits 0 on pass. The prescan times it as the shift's baseline and refuses a run over 10 minutes.
- **The verify recipe**, `verify/recipe.md`, the verifier's instructions (map #7), its sections in this order:
  - **Launch**: refuse if the config's port already answers to `playwright-cli`, start the app the way the config does in the background, poll with `playwright-cli` until it answers. No `curl`, `lsof` or `kill`: a shift's allow list does not carry them.
  - **Drive**: explore with `playwright-cli`; find a region by its role, or by its visible label when it has none; read app code to learn how a term looks on the page, never edit it.
  - **Clean up**: stop the app's background task and close the browser before any model-free run, which needs the same port.
  - **Evidence**: one test per criterion, `e2e/<ticket>-<k>.spec.ts`, titled with the criterion's THEN clause, one `expect` per thing it names, data read from the fixture at run time, one screenshot saved to `verify/evidence/<ticket>/<k>.png`; run with `npx playwright test <file> --reporter=json`, report saved as `verify/evidence/<ticket>/report.json` with machine paths stripped.
  - No `## Proven` section: step 11 writes it.

Whenever the recipe is new, also draft **the setup test**, `e2e/setup.spec.ts`, by following the drafted recipe yourself: one thing the app's home page plainly shows (a heading, a list's count), one `expect`, written as the Evidence section says, except that its screenshot goes to `test-results/setup.png`, which is git-ignored, so a run never dirties the tree. It is what step 11 proves the recipe with, and stays as a regression test. Show it for approval like the rest.

## 11. Prove the recipe

Check first; this changes nothing:

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/cli/recipe" proven
```

`proven` set and `changed` empty, and nothing was drafted in step 10: the recipe is proven and unchanged; go to step 12. Otherwise (no Proven commit, or the recipe or Playwright config changed since it) prove it, with the setup test or, for an existing recipe, a test under `e2e/` the builder names:

1. Run `verify/checks` in the foreground. It must pass on the working app; if it fails, show the output and stop: a recipe cannot be proven against a red baseline.
2. **Propose one small deliberate break** in app code, tied to exactly what the test checks (for example, cut a list from 3 items to 2, or change the heading's text). Show the diff and ask the builder to approve it. The builder approves; never ask them to write it. Declined: propose another.
3. Make the break in a scratch copy of the working tree, drafts and `node_modules` included, so the builder's tree is never touched (map #16):

   ```
   S="$(git rev-parse --absolute-git-dir)/third-shift/prove"; rm -rf "$S"; mkdir -p "$S"; rsync -a --exclude .git ./ "$S/"
   ```

   Apply the approved break in `$S`, run only that test there (`cd "$S" && npx playwright test <file>`), then remove the copy with `rm -rf "$S"`, which reverts the break. Remove it on every path, a failed run or a decline included. Confirm with `git status --porcelain` that only the approved files from steps 9–10 differ from HEAD.
4. Show the failing output and ask the builder to confirm the failure **names the thing the test is about** (`expected 3, received 2`). A pass, or a failure for another reason (a timeout, a build error, a missing page), proves nothing: say so and go back to 2.
5. Run the test again in the working tree: it must pass on the unbroken app.

## 12. Commit

1. If steps 9–10 changed files, stage exactly those files (`git add <each file>`, never `-A`), show `git diff --cached --stat`, and commit them as `third-shift: setup`.
2. Only if step 11 proved the recipe in this run (otherwise the Proven record already names the right commit; skip to 3): record the proof against the commit that holds the proven recipe, which is now HEAD. The note is one line: the break and the failure line it produced.

   ```
   uv run --script "${CLAUDE_PLUGIN_ROOT}/cli/recipe" proven --commit HEAD --note "<break>: <failure line>"
   ```

   It writes `## Proven` at the end of the recipe and reads it back with the prescan's own check; a refusal means the files at HEAD are not the ones proven: show it and stop. Commit the recipe as `third-shift: setup proven`. The Proven commit cannot name the commit that carries it, so the proof is its own commit after the files (#31).
3. Nothing committed in 1–2: nothing to push; say so.
4. Otherwise show the commits and ask to push. On yes, `git push origin HEAD:<default branch>`. If GitHub refuses it as a protected branch (or a ruleset), push the same commits to `third-shift/setup` instead and open a pull request with `gh pr create --base <default branch> --head third-shift/setup --title "third-shift: setup"`. Tell the builder to merge it **with a merge commit, never squash or rebase**, which would drop the Proven commit from the default branch, and to rerun `/third-shift:setup` after merging. A refusal for any other reason (the remote moved on) stops with its message; nothing is forced.

## 13. Allow the target's commands

A shift refuses every prompt, and the allow list cannot name a target's own commands (map #4). Read `verify/checks`, `package.json`'s scripts and the recipe's Launch section for the suite command (the one a brief's `{test_cmd}` will name, such as `npm test`) and the command that starts the app. Show them, and what this would add (it changes nothing):

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/cli/settings" --allow "Bash(<test command>*)" --allow "Bash(<launch command>*)"
```

Its `add` lists only what is missing; empty: in place already. Otherwise ask; on yes, rerun it with `--write`. A refusal: show it and stop.

## Summary

End with one line per step: in place already, changed, declined, or advised, and anything the builder still has to do before a shift.
