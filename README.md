# third-shift

An unattended software factory for Claude Code. You plan with
[Matt Pocock's skills](https://github.com/mattpocock/skills) (`wayfinder`, `to-spec`,
`to-tickets`); third-shift picks up where `to-tickets` stops. It checks that every ticket
carries enough to build from, asks you its questions in one sitting, then works the tickets
while you are away — a fresh implementer and reviewer per ticket — and leaves a handover.
It runs inside Claude Code on your subscription, not the API.

**Direction.** third-shift is pre-release. Version 1 is serial: it works one spec's tickets one at a time while you're away, verifies each with evidence, pauses before the usage limit and resumes after reset, and leaves a handover. Beyond version 1, the aim is a release factory rather than a build step:

- **Parallel work:** two agents at once, then bursting to use spare plan capacity.
- **More kinds of project:** verify recipes for native iOS apps and Dockerized services, after web.
- **Deployment for review:** each verified change deployed to a test or staging environment where you can try it.
- **Release documentation:** written from the shift's own records.

None of these is built or committed to yet.

**Status: pre-release.** The `start` skill is the working shift it grew out of.
Verification gates, the progress board and the usage gate are being designed; parallel
work comes after version 1; see [docs/ideation/factory-research.md](docs/ideation/factory-research.md). Why it
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
