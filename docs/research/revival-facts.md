# Two facts revival depends on

Research for issue #13, part of the v1 map (#1). It backs crash revival (#10): a recurring
scheduled task in the Claude desktop app starts a shift again in a fresh session when no
heartbeat has arrived for 20 minutes.

Checked 2026-11-17 against Claude Code 2.1.312 and the docs at code.claude.com.

## The answers

**1. Do hooks fire inside subagents, and do they say which agent made the call?**
Yes on both counts. We tested it as well as reading the docs. When a subagent uses a
tool, the same `PreToolUse` and `PostToolUse` hooks fire as in the main conversation.
Plugin hooks fire too, which matters because third-shift is a plugin. The data passed
to the hook carries `agent_id` (a unique id for that subagent run) and `agent_type` (for
example `general-purpose`). Both are missing when the main conversation makes the call.
Separate `SubagentStart` and `SubagentStop` events exist. So a heartbeat written from
`PreToolUse` keeps beating while an implementer subagent works. A long implementer step
does not go silent just because it is inside a subagent.

The heartbeat can still go quiet in one case: a single tool call that runs a long time,
such as a slow test suite. The hook fires when the call starts and again when it ends,
and nothing fires in between. If that gap exceeds 20 minutes, revival reads it as a
death. See the caveats for what to do about it.

**2. Can a session started by a scheduled task turn on Remote Control for itself?**
Almost certainly not by itself. It doesn't need to, though.

- The desktop app's tool for switching Remote Control (`set_remote_control`) says in its
  own description that it is "refused for sessions started from another device and
  unattended ones". It also needs the user's approval on a card. A session started by a
  scheduled task is unattended, so it can't switch itself on.
- The desktop app has a setting, **Connect new sessions to Remote Control** (Settings >
  Code), that connects new sessions to Remote Control as they start. On this machine it is
  already **On**.
- **The least the builder must do:** leave that setting on, once, by hand. A revived
  shift should then appear on the phone under claude.ai/code or in the Claude app, with
  no further steps. If a revived shift doesn't appear, the fallback is to open its
  session on the desktop and switch on its **Remote Control** switch, or type
  `/remote-control`, which needs someone at the computer.
- **Not verified:** whether that setting applies to sessions started by scheduled tasks
  as well as ones the builder starts. The docs describe the setting as covering "new
  sessions" and say nothing about scheduled ones. No scheduled task exists on this
  machine to check with. One test run settles it, see below.

## Evidence

### Question 1: hooks inside subagents

**Docs.** The hooks reference (https://code.claude.com/docs/en/hooks):

- On subagents: "When a subagent calls a tool, tool events such as `PreToolUse` and
  `PostToolUse` fire the same configured hooks as in the main conversation, and the input
  carries the `agent_id` and `agent_type` common input fields that identify the subagent."
  Hooks from settings files, managed settings and plugins all run inside subagents.
- `agent_type` is "Present when the session uses `--agent` or the hook fires inside a
  subagent."
- `SubagentStart` fires "When a subagent is spawned", and `SubagentStop` fires "When a
  subagent finishes". Both can match on agent type.
- The page has no heartbeat event. The nearest events are `Notification` (for example
  `idle_prompt`) and `TeammateIdle`, and neither fits.

Changelog (https://code.claude.com/docs/en/changelog), 2.1.327, fixed failing
`SubagentStop` hooks in background agents showing nothing. That shows the event is also
wired up for background subagents.

**Test.** We made a throwaway folder with local hook settings that logged every
`PreToolUse`, `SubagentStart` and `SubagentStop` input. We then ran `claude -p` with a
prompt that spawns one subagent, which runs one `echo` command. Four events were logged,
in this order. Paths are redacted, and the ids belong to the throwaway run.

| Event | Tool | `agent_id` | `agent_type` | Notes |
|---|---|---|---|---|
| `PreToolUse` | `Agent` | none | none | the main conversation spawning the subagent |
| `SubagentStart` | n/a | `a2e28d…` | `general-purpose` | |
| `PreToolUse` | `Bash` | `a2e28d…` | `general-purpose` | **the subagent's own tool call fired the hook** |
| `SubagentStop` | n/a | `a2e28d…` | `general-purpose` | also carries `agent_transcript_path` and `last_assistant_message` |

All four events carry the parent's `session_id` and the parent's `transcript_path`. A
heartbeat can therefore tie every event to the shift's session without extra work. The
subagent's own transcript file is named only in `SubagentStop`.

### Question 2: Remote Control for a scheduled session

- Desktop app tool `set_remote_control`, from the tool description in this session's
  tool list. We read it and didn't call it. It switches "the toolbar's Remote Control
  switch" for "self" or another session and asks the user to approve. It "Needs a session
  that has run a turn; refused for sessions started from another device and unattended
  ones."
- Desktop app tool `get_settings`, a read-only call. It lists
  `connect_new_sessions_to_remote_control`, "Whether sessions the user starts on this
  computer connect to Remote Control automatically", which is currently `true`. It also
  lists the terminal setting `remoteControlAtStartup` as not set, and notes that the
  desktop app's own switch "wins when set".
- Desktop docs (https://code.claude.com/docs/en/desktop, section "Control which sessions
  appear on your other devices"): "new sessions connect automatically while **Connect
  new sessions to Remote Control** is on". The page doesn't mention scheduled tasks in
  connection with Remote Control.
- Remote Control docs (https://code.claude.com/docs/en/remote-control): the desktop app
  turns it on per session with `/remote-control` or the auto-connect setting.
  `remoteControlAtStartup: true` counts only in user or managed settings. In a project's
  `.claude/settings.json` "It ignores a `true`", so the plugin or repo can't switch it
  on for the builder. A `false` there turns it off for that repo. Remote Control also
  stops when the desktop app quits, and "Presence heartbeats" can drop after about 30
  minutes without contact.
- Scheduled tasks docs (https://code.claude.com/docs/en/desktop-scheduled-tasks): each
  run "starts a fresh session" while the app is open and the computer is awake. You
  reach a run's session from the task's History list or the sidebar's Scheduled group,
  where you "respond to permission prompts". Remote Control isn't mentioned.
- The changelog shows no command-line flag or setting that turns on Remote Control for
  scheduled runs alone.

## Caveats and what wasn't verified

1. **A long single tool call looks like death.** The hooks fire before and after a call,
   never during it. Under the 20-minute rule, a long test or build run inside one call
   is the false-death case, whether or not a subagent made it. Cheap ways round it:
   - also treat a recent change to the session's transcript file (`transcript_path`) as
     a sign of life;
   - have the shift run long commands in the background, so hooks keep firing;
   - make the window longer than the longest single call a shift may make.

   The transcript file's last-changed time probably doesn't move during a single long
   call either. We didn't test that.
2. **Q1 was tested with the command-line client (`claude -p`), not in a desktop app
   session.** The desktop app's Code tab runs the same Claude Code and reads the same
   settings and plugin hooks, so we expect the same result. We didn't observe it there.
3. **Q2's key fact is unconfirmed.** We don't know whether a session started by a
   scheduled task connects through **Connect new sessions to Remote Control**. To
   settle it, create a manual scheduled task, click **Run now**, then check the run's
   session. Its Remote Control switch, or the `remoteControlState` field from
   `get_session`, shows whether it connected. We didn't create a task, because this
   research changes no settings or sessions.
4. **The "unattended" refusal comes from a tool description, not a docs page.** It's
   first-party, because the desktop app supplies it, but it may change without a
   changelog entry.
5. **Related finding:** changelog 2.1.325 says scheduled tasks now "ask before running a
   skill that declares `allowed-tools` or hooks". To run unattended, add `Skill(name)`
   to `permissions.allow`. A revived shift that starts a third-shift skill will stall on
   that prompt unless the allow rule is in place.
6. A revived shift visible on the phone can still stall on permission prompts. The
   builder can answer those from the phone over Remote Control, but only if the session
   connected.
