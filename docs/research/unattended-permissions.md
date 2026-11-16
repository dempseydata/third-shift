# Unattended permissions: what lets a shift run without prompts, and what it must never do

Research for [#4](https://github.com/dempseydata/third-shift/issues/4), part of the map [#1](https://github.com/dempseydata/third-shift/issues/1). Run 2026-11-16 against the Claude Code docs at `code.claude.com/docs` and Apple's support pages and manual pages. Nothing was installed, and no setting was changed. Claims are cited inline. **Not confirmed** marks anything no source states.

## The answer in brief

1. **Auto mode is close, but not enough on its own.** It runs most of a shift without prompts, but it allows a push to the default branch by default. It also drops back to prompting after 3 blocks in a row or 20 in a session. Ask rules, `AskUserQuestion` and a few dangerous deletes still need a person.
2. **Add one user setting: `permissions.denyInsteadOfPrompting: true`.** It turns every would-be prompt into a refusal, so the shift keeps going instead of waiting until morning. The cost is that it also removes `AskUserQuestion` in every session, attended ones included. The `start` skill uses that tool today.
3. **Guard the shift with a PreToolUse hook, not with deny rules alone.** A Bash deny rule matches the start of a command, and the docs say it is not a security boundary. A hook reads the full command and can refuse a push to the default branch, a force push, a branch or issue delete, and work outside the repo. A hook's block holds in every mode.
4. **Remote Control can see and set the permission mode** (Manual, Accept edits, Plan or Auto, not Bypass) for a session the desktop app hosts. Prompts left open can be answered from the phone.
5. **Keep-awake prevents idle sleep only.** A closed lid sleeps the Mac, and a local session sleeps with it. The Mac must stay on power with the lid open, or closed only with an external display, keyboard and mouse attached. Turn on the desktop app's **Keep computer awake** and macOS's **Prevent automatic sleeping on power adapter when the display is off**.

## 1. Is auto mode enough?

How auto mode decides, in order ([permission-modes](https://code.claude.com/docs/en/permission-modes.md#how-the-classifier-evaluates-actions)):

1. Allow, ask and deny rules resolve first.
2. Reads and edits inside the working directory are approved without the classifier, except writes to protected paths.
3. Everything else goes to a classifier. A block is reported to Claude, which carries on.

What it **allows** that a shift must not do:

- "By default in auto mode, Claude can push to the repository you're working in, including its default branch, without a prompt" ([auto-mode-config](https://code.claude.com/docs/en/auto-mode-config.md#common-boundaries)). The shift's rule against default-branch pushes needs a hook (section 3).
- A narrow Bash allow rule, such as `Bash(git push *)`, is resolved **before** the classifier. A destructive argument the prefix did not anticipate therefore never reaches the classifier ([auto-mode-config, Suspend shell allow rules](https://code.claude.com/docs/en/auto-mode-config.md#suspend-shell-allow-rules)). `autoMode.classifyAllShell: true` sends every shell command to the classifier instead, at some cost in speed.

What it **blocks** by default and is relevant here ([permission-modes, blocked by default](https://code.claude.com/docs/en/permission-modes.md#what-the-classifier-blocks-by-default)):

- force push, and deleting remote branches, tags or releases;
- `git reset --hard`, `git checkout -- .`, `git restore .`, `git clean -fd`, `git stash drop`;
- "Irreversibly destroying files that existed before the session";
- merging a pull request no human approved;
- `rm -rf "$VAR"` where the variable is not set in the visible conversation;
- **outbound text to a public repo that carries sensitive details.** The docs name "internal file paths" and say issue comments and commit messages count. Third-shift's tracker is public, so a resolution comment that quotes a machine path can be blocked. The shift should write comments without machine paths.

What it **still stops on**:

| Stop | What happens | Source |
| --- | --- | --- |
| 3 blocks in a row, or 20 in a session | Auto mode pauses and prompting resumes. Not configurable. | [permission-modes](https://code.claude.com/docs/en/permission-modes.md#when-auto-mode-falls-back) |
| A matching `ask` rule | Prompts in every mode | [permission-modes](https://code.claude.com/docs/en/permission-modes.md#actions-no-mode-auto-approves) |
| `AskUserQuestion` | Always waits for a person | same |
| A critical-path `rm` or `rmdir` | No allow rule or hook can approve it | same |
| Workspace trust dialog, project MCP approval | Waits even with the deny-instead setting on | [settings-reference](https://code.claude.com/docs/en/settings-reference.md#permissions-denyinsteadofprompting) |

Auto mode applies to subagents, and a subagent's own `permissionMode` frontmatter is ignored ([permission-modes](https://code.claude.com/docs/en/permission-modes.md#eliminate-prompts-with-auto-mode), [sub-agents](https://code.claude.com/docs/en/sub-agents.md#permission-modes)). A background subagent's prompt surfaces in the main session ([sub-agents](https://code.claude.com/docs/en/sub-agents.md#run-subagents-in-foreground-or-background)).

In the desktop app the mode is picked in the selector under the prompt box. The pick is remembered per folder ([desktop](https://code.claude.com/docs/en/desktop.md#choose-a-permission-mode)). `"defaultMode": "auto"` takes effect only from `~/.claude/settings.json` or managed settings, never from a project's `.claude/` files ([permission-modes](https://code.claude.com/docs/en/permission-modes.md#which-mode-a-session-starts-in)).

### Turning prompts into refusals

`permissions.denyInsteadOfPrompting: true` "denies a tool call that would otherwise wait on a prompt, and the turn continues". It needs v2.1.319 or later. It can be set only in user or managed settings, never by a repository. It applies to local desktop sessions and to subagents ([settings-reference](https://code.claude.com/docs/en/settings-reference.md#permissions-denyinsteadofprompting)). The docs' own example pairs it with `"defaultMode": "auto"`.

What it also removes: `AskUserQuestion`, `EnterPlanMode` and `ExitPlanMode` (same source). Because it lives in user settings, this applies to the builder's attended sessions too. The `start` skill's decision sitting and its blocked-ticket sitting both use `AskUserQuestion` today.

**Not confirmed:** what happens after auto mode's 20-block fallback with this setting on. Each later classifier-routed call may be refused for the rest of the session, because nothing approves the prompt that would resume auto mode. Test it before relying on a long night.

### The other modes

- **`dontAsk`** never waits, but it refuses everything outside the allow list, and it denies writes to protected paths, `.git` among them ([permission-modes](https://code.claude.com/docs/en/permission-modes.md#allow-only-pre-approved-tools-with-dontask-mode)). **Not confirmed:** whether `git commit` through Bash counts as a protected-path write. It is a worse fit than auto plus the deny-instead setting, because every command the shift runs would need listing.
- **`bypassPermissions`** skips the classifier as well as the prompts. The docs say to use it "only ... in isolated environments", and it cannot be chosen from Remote Control. Not recommended.

## 2. Allow and deny rules

Rules are checked deny, then ask, then allow. The first match wins, and an allow never carves an exception out of a deny ([permissions](https://code.claude.com/docs/en/permissions.md#manage-permissions)). Two limits matter here:

- A Bash rule "doesn't match the same program invoked in a different form". `Bash(git push *)` misses `git -C . push`, and `Bash(curl *)` misses `/usr/bin/curl` ([permissions](https://code.claude.com/docs/en/permissions.md#what-a-bash-rule-doesnt-match)). Deny rules are a backstop.
- A hook's `"allow"` cannot override a deny rule ([permissions](https://code.claude.com/docs/en/permissions.md#precedence-among-rules-hooks-and-mods)). A blanket `Bash(git push *)` deny would also block the shift's legitimate push of its build branch. Pushes therefore belong to the hook.

**Recommended deny set** (backstop; user settings). These are actions the shift never needs:

```json
{
  "permissions": {
    "deny": [
      "Bash(git push --force *)", "Bash(git push -f *)", "Bash(git push --force-with-lease *)",
      "Bash(git push --delete *)", "Bash(git branch -D *)",
      "Bash(gh repo delete *)", "Bash(gh issue delete *)", "Bash(gh release delete *)",
      "Bash(gh pr merge *)", "Bash(gh repo edit *)", "Bash(gh api -X DELETE *)"
    ],
    "blockWritesOutsideWorkingDirectories": true
  }
}
```

`blockWritesOutsideWorkingDirectories` makes Write, Edit and NotebookEdit refuse paths outside the working directories in every mode. It needs v2.1.314 or later. It does **not** limit shell commands ([permissions](https://code.claude.com/docs/en/permissions.md#block-file-tool-reads-and-writes-outside-the-working-directories)).

**Recommended allow set:** keep it narrow, and put it in user settings. A skill's `allowed-tools` frontmatter is not the place for it. It grants tools only "during the turn that invokes this skill", and "the grant clears when you send your next message" ([skills, frontmatter reference](https://code.claude.com/docs/en/skills.md)). The builder's first reply through Remote Control would therefore drop it. The rules:

```
Bash(git status *) Bash(git diff *) Bash(git log *) Bash(git add *) Bash(git commit *)
Bash(git switch *) Bash(git checkout -b *) Bash(git push origin night-shift/*)
Bash(gh issue view *) Bash(gh issue list *) Bash(gh issue comment *) Bash(gh issue close *) Bash(gh issue edit *)
```

Add the target project's test and checks commands. These are project-specific, and the prescan would name them. Most would pass the classifier anyway, but every classifier block counts towards the 3-and-20 limits, so fewer classifier calls means fewer chances to trip them. Because allow rules skip the classifier, the guard hook has to cover them.

The same frontmatter offers `disallowed-tools`, which removes a tool such as `AskUserQuestion` "for a background loop" while the skill is active (same source). It clears on the next message in the same way.

## 3. The guard hook

The docs' own advice for full-command inspection is a PreToolUse hook ([permissions](https://code.claude.com/docs/en/permissions.md#what-a-bash-rule-doesnt-match)).

- **How it blocks.** Exit code 2 (stderr becomes the reason Claude reads), or JSON `hookSpecificOutput.permissionDecision: "deny"` ([hooks](https://code.claude.com/docs/en/hooks.md#pretooluse-decision-control)). "A hook that exits with code 2 stops the tool call before permission rules are evaluated." So it beats allow rules. "A call that a PreToolUse hook blocked stays blocked, whichever settings file the hook comes from" ([permissions](https://code.claude.com/docs/en/permissions.md#precedence-among-rules-hooks-and-mods)).
- **Where it runs.** Hooks fire in the desktop app, and PreToolUse fires for subagent tool calls too ([hooks](https://code.claude.com/docs/en/hooks.md)).
- **Where to declare it.** In the `start` skill's frontmatter. A skill hook is registered when the skill is invoked and stays for the rest of that session ([hooks, Hooks in skills and agents](https://code.claude.com/docs/en/hooks.md)), so it guards shifts and leaves the builder's other sessions alone. Plugin skills keep their frontmatter hooks even under a plugin-only lock (same source). The script lives in `cli/` and is run from the plugin, as the repo's CLAUDE.md already requires. **Not confirmed:** that a skill-registered hook fires for subagents' calls. The docs say subagent calls fire "the same configured hooks"; test it in the prototype.
- **Fail closed.** A timed-out PreToolUse command does not block ([hooks, timeouts](https://code.claude.com/docs/en/hooks.md#timeouts)). Keep the script fast, deterministic and free of the network.

What the hook should refuse on `Bash` (matcher `Bash`):

1. any `git push` whose destination is the default branch: `main`, `master`, `HEAD`, or the branch `gh repo view --json defaultBranchRef` reports, read once at setup and kept in the ledger rather than queried per call;
2. any push with `--force`, `-f`, `--force-with-lease`, `--delete`, `--mirror`, or a `:branch` refspec;
3. `git branch -D`, `git push --tags`, `git remote add` or `set-url`, and `git config` writes;
4. `gh repo`, `gh release`, `gh pr merge`, and `gh issue delete`, `transfer` or `lock`, plus `gh api` with any method other than GET;
5. any absolute path, `~` or `..` that resolves outside the repo or worktree, in `rm`, `mv`, `cp`, `cd` or a redirect, plus `sudo` and `curl | sh`.

On `Write|Edit` it should refuse paths outside the repo, which duplicates `blockWritesOutsideWorkingDirectories` for older builds.

This is a careful guard, not a sandbox. A determined `sh -c "$(echo ...)"` can slip past text inspection. The OS-level boundary for shell commands is the sandbox, which restricts Bash writes to the working directory and limits network to an allowlist ([sandboxing](https://code.claude.com/docs/en/sandboxing.md)). `git push` and `gh` would need `github.com` and `api.github.com` on that allowlist. **Not confirmed:** that the sandbox runs in desktop-app sessions. It is worth a test, not a dependency for version 1.

One more caveat: on a personal (non-managed) login, an installed **mod** "can approve a call that a deny rule refuses or a PreToolUse hook blocked" ([permissions](https://code.claude.com/docs/en/permissions.md#precedence-among-rules-hooks-and-mods)). Do not run shifts with a mod that approves tool calls.

## 4. Remote Control and the permission mode

- **Set and see:** a Remote Control session on the local machine offers "Manual, Accept edits, Plan, and Auto"; "you can't select Bypass permissions from the app". The dropdown shows the live mode, including one set elsewhere, and desktop-hosted sessions "report permission mode changes to claude.ai as they happen" ([permission-modes, Web and mobile](https://code.claude.com/docs/en/permission-modes.md#switch-permission-modes)). A prescan step can therefore ask the builder to confirm Auto from the phone. Whether the agent itself can read its mode is **not confirmed** from a doc.
- **Answer:** "Claude Code keeps permission prompts and `AskUserQuestion` questions open until you answer them" ([remote-control, limitations](https://code.claude.com/docs/en/remote-control.md#limitations)). Turn on **Push when actions required** to be notified of prompts and questions on the phone ([remote-control, push notifications](https://code.claude.com/docs/en/remote-control.md#mobile-push-notifications)). With `denyInsteadOfPrompting` on, there is nothing to answer: the call is refused and the shift moves on.
- **Settings:** `/permissions`, `/plugin` and other terminal-only commands are not available from the phone (same source). Allow and deny rules and the auto-mode config are edited on the Mac, in `~/.claude/settings.json`. The desktop app's `/permissions` has no Auto mode tab ([auto-mode-config](https://code.claude.com/docs/en/auto-mode-config.md#edit-rules-from-permissions)).
- **Sleep:** "if your laptop sleeps ... Claude Code reconnects automatically when your machine comes back online" ([remote-control](https://code.claude.com/docs/en/remote-control.md)). Reconnecting is not working, though: a local session does no work while the Mac sleeps.

## 5. Keeping the Mac awake

- **The app's per-session hold** prevents idle sleep only. "A closed lid still sleeps, and so does choosing Sleep." It ends when the session stops or the app quits. With `session_idle` it "lets go once the session has been idle for about 5 minutes". The source is the desktop app's own keep-awake tool description, read in-session; no published doc states this.
- **The app-wide setting:** "turn on **Keep computer awake** in **Settings > Desktop app** or **Settings > This computer > System**. Closing the laptop lid still puts it to sleep" ([desktop-scheduled-tasks](https://code.claude.com/docs/en/desktop-scheduled-tasks.md#how-scheduled-tasks-run)). Unlike the per-session hold, this does not release when a session goes quiet. That matters for a shift paused for a usage reset.
- **macOS:** System Settings > Battery > Options > **Prevent automatic sleeping on power adapter when the display is off** applies on a power adapter only ([Apple: Set sleep and wake settings](https://support.apple.com/guide/mac-help/set-sleep-and-wake-settings-mchle41a6ccd/mac)). `caffeinate -s` holds off system sleep "only when system is running on AC power"; `-i` holds off idle sleep (`man caffeinate`). The display may sleep freely, because display sleep is not system sleep (`man pmset`).
- **Lid closed:** Apple supports it only on power with an external keyboard and mouse and a display connected ([Apple 102501](https://support.apple.com/en-us/102501), [Apple 117373](https://support.apple.com/en-us/117373)). Without those, closing the lid sleeps the Mac.
- **Battery:** **not confirmed** whether the app's hold survives a long night on battery, or what macOS does near empty. Plan for mains power.
- **Restarts:** "A restart of Desktop or of your computer, including for an update, counts as a quit" ([desktop](https://code.claude.com/docs/en/desktop.md#keep-a-task-running-while-desktop-is-disconnected); that section is written for SSH sessions, so its read-across to local sessions is inferred). Overnight macOS or app auto-updates can end a shift.

**What the builder sets on the Mac before a night shift:**

1. Plug into power.
2. Leave the lid open, or close it only with an external display, keyboard and mouse attached.
3. Claude desktop: Settings > Desktop app > **Keep computer awake** on.
4. macOS: Battery > Options > **Prevent automatic sleeping on power adapter when the display is off** on.
5. Make sure no macOS or app update is scheduled to install overnight.
6. Leave Claude desktop running and signed in.

## Open questions worth a prototype

1. Does auto mode's 20-block fallback, combined with `denyInsteadOfPrompting`, leave the rest of a session refusing everything?
2. Does a hook registered by the `start` skill fire for calls its subagents make?
3. Does the sandbox run in a desktop-app local session?
4. Can the shift read its own permission mode, to refuse to start outside Auto?
