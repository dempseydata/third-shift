# third-shift

An unattended software factory for Claude Code: it works the agent-ready tickets that Matt Pocock's to-tickets produced, verifies each one, and leaves a handover. For a solo builder running on a Claude subscription.

## Visibility
**Born public.** This repo is the public repo — there is no private working copy and no
export step. Everything committed here is publishable from the first commit:

- The working record — everything under `docs/`: ideation, definition, design comps, the why,
  build ledgers and `docs/adr/` — is public by design. Write it knowing that.
- Real session-derived data, fixtures drawn from it, unfiltered screenshots, secrets and
  machine paths never enter git. `local-data/` is ignored for the first; screenshots are
  taken from a filtered or synthetic view; issue bodies reference sessions by id, never
  quoted transcript text from another project.
- Toolchain is plugins at user scope plus `~/.claude/skills/`. Nothing under `.claude/` is
  tracked here: project settings are tooling, kept local.
- `.githooks/pre-commit` refuses a commit that matches `.githooks/denylist.txt` (home
  paths, key shapes, transcript filenames) or a private-project name listed in
  `~/.config/git/denylist-private.txt`, a file kept outside every repo so the names are
  never published; the hook warns while it has none. Add to the lists; do not bypass it.

Issues live on this repo and are public. Publication is therefore not a phase — the repo
flips visibility on GitHub when the README says what the product is and `security-preflight`
has run. If a product cannot meet this, it is a private-forever project and starts from
`project-template/`, not from here. A product that isn't a skill or plugin starts from
`project-template-public/`.

## Shape
**A Claude Code plugin; the repo root is the plugin root**, so the root reads as the product:

```
.claude-plugin/plugin.json, marketplace.json   the plugin; the repo is its own marketplace
skills/<name>/                                 one folder per skill: SKILL.md, references/, scripts/
cli/                                           only if there is deterministic code
evals/                                         the eval set for `claude plugin eval`
docs/ CONTEXT.md                               the record
```

- A skill folder holds the skill's text and what it alone uses. Deterministic work shared by
  skills lives in `cli/` and is run from the plugin (`<skill-dir>/../../cli/...`), never from
  PATH, so a plugin install is the whole install; a first run installs anything missing.
- Every skill is written to `writing-great-skills`: decide model- or user-invoked first.
- The prompt is the product, so Evaluation applies from the first skill: `evals/` holds the
  frozen set, `claude plugin eval` runs it.
- `claude plugin validate` gates every commit (the pre-commit hook). A release bumps
  `version` in `plugin.json` and is tagged with `claude plugin tag`.
- Two install routes, one per machine: the plugin for users (`claude plugin marketplace add`
  then `claude plugin install`), a symlink from `~/.claude/skills/<name>` into `skills/<name>`
  for working on a skill. Both installed means two live copies.

## Phase layout
`docs/ideation/` → `docs/definition/` → `docs/design/` → `skills/` (and `cli/`).
Context from earlier phases informs later ones — don't engage on design without reading the
definition, don't engage on build without reading the design decisions. `docs/why.md`
is the story the README used to tell: why it was built, how, and what was reversed.

## Stack conventions
- Domain vocabulary → `CONTEXT.md`. Decision rationale → `docs/adr/`. Reviewability docs
  (`architecture`, `flows`, `permissions`, `variables`, …) → `docs/`, from `/document-app`.
- `diagnosing-bugs` and `improve-codebase-architecture` must read `CONTEXT.md` + `docs/adr/` first.

There is no house DESIGN.md; a product's root `DESIGN.md`, if any, is derived from its shipped UI for Impeccable's drift detection, never a source of truth.

## Design skills
Only if the plugin ships a visual surface. `taste-skill:design-taste-frontend` (the `taste-skill@taste-skill` plugin, user scope, nothing copied into the repo) is the taste-skill fallback — it draws candidate directions from its own internal library, not a named-variant pick; `impeccable` fine-tunes only after a direction is chosen.
