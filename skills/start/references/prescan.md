# Prescan

Two halves. A read-only script runs every mechanical check and writes `prescan.json`; one read-only subagent, from the prescan brief, does the judgement: decision gaps and each criterion against the verify recipe. Together they settle, before arming, everything that would otherwise stop the shift at 2 a.m.

## 1. Read the project's rules

Read the target's root `CLAUDE.md` or `AGENTS.md`, `docs/agents/domain.md` (where ADRs live and their format) and `docs/agents/triage-labels.md`. The project's own rules (visibility, hooks, paths that never enter git) come from these, and every brief carries them as `{project_rules}`.

## 2. Run the script

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/cli/prescan" --spec <n> --out .git/third-shift/prescan.json
```

- **Refused** (exit 1: no sub-issues, an unmerged `third-shift/<spec-slug>` branch, an unreadable tracker): show the `refused` text and stop. Nothing was written.
- **Done**: read `.git/third-shift/prescan.json` (its shape is documented at the top of `cli/shift`).

## 3. Failed checks stop the start

Each entry in `checks` has `name`, `ok` and `detail`; a failed one's detail ends with `run /third-shift:setup`. Arm refuses on any failed check, so a failed check is not a sitting question:

- Any failed check other than `mains power`: show every failed check with its detail and stop before the brief. The builder runs `/third-shift:setup` and starts again.
- This covers a target with no `verify/recipe.md`: the `recipe proven` check fails and names setup, so the prescan brief, which reads the recipe, never runs without one.
- `mains power` carries `"mode": "away"`: failed, it only takes away mode off the sitting.

## 4. Collect the binding sources

Every ADR in the target, every closed issue or decision ticket the spec and its tickets cite, the spec itself, and the docs they point to. Precedence: ADRs, then closed decision tickets, then the spec, then everything else only where those are silent. This list fills the brief's `{sources}` and becomes sitting.json's `binding_sources`.

## 5. Spawn the prescan brief

One fresh foreground subagent from the Prescan brief in [briefs.md](briefs.md), with the Prescan row of its role table (`model: opus`, effort high). Fill `{spec}`, `{sources}` and `{tickets}` (from prescan.json; paste, never a path into this skill). If it comes back in the background, wait for its completion notice before going on.

Its usage is not recorded: no shift is armed yet, so there is no ledger to cost it against and no gate to pass (`admit` and `step` need an armed shift), and the builder is at the Mac. The role table's Prescan starting cost is a guess kept for reference only.

## 6. Report

Show the builder, then move to the sitting:

- the ticket table: number, title, state, class (from the label and the brief), native blocking edges;
- the binding sources, in precedence order;
- each check's result, and prescan.json's `warnings`;
- the baseline (`baseline_seconds`) and the recipe's Proven commit;
- prescan.json's `questions`, and the brief's gaps, each with its recommendation.
