# third-shift

An unattended software factory for Claude Code. You plan with
[Matt Pocock's skills](https://github.com/mattpocock/skills) (`wayfinder`, `to-spec`,
`to-tickets`); third-shift picks up where `to-tickets` stops. It checks that every ticket
carries enough to build from, asks you its questions in one sitting, then works the tickets
while you are away — a fresh implementer and reviewer per ticket — and leaves a handover.
It runs inside Claude Code on your subscription, not the API.

**Status: pre-release.** The `start` skill is the working night shift it grew out of.
Verification gates, the progress board, parallel tickets and the usage gate are being
designed; see [docs/ideation/factory-research.md](docs/ideation/factory-research.md). Why it
exists is in [docs/why.md](docs/why.md).

## Install

Requires [Claude Code](https://claude.com/claude-code) and the `mattpocock-skills` plugin,
with `/setup-matt-pocock-skills` run once in the repo you want built.

```bash
claude plugin marketplace add dempseydata/third-shift
```

```bash
claude plugin install third-shift@third-shift
```

Invoke `/third-shift:start` with a spec. Update with `claude plugin update third-shift@third-shift`.

## Develop

To work on a skill, link it instead of installing the plugin — one route per machine:

```bash
ln -s "$PWD/skills/start" ~/.claude/skills/start
```

Edits take effect in the next session.

## License

[MIT](LICENSE).
