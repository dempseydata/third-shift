# Research: can a shift move cards on a GitHub Projects board?

Question (issue #3): can an unattended shift add issues to a GitHub Projects (v2) board and move
them between columns with the scopes a normal `gh auth login` grants, or does it need the
`project` scope or a separate token? What must the builder set up once, can a script do any of
it, and is the board usable from the GitHub mobile app?

Researched 2026-11-16 against GitHub's docs, the `gh` 2.92.0 help text, and the live GraphQL
schema (read by introspection). Nothing was created, changed or deleted, and no token was
refreshed.

## Answer

**No, the ordinary login is not enough. One extra scope, `project`, is needed, added once.**
After that, a script can do everything the shift needs: add issues, move cards between columns,
and even build the board itself. The only things a script cannot do are switch on GitHub's
built-in board automations, which are a few clicks in the browser and mostly optional. The board
can be read and its cards moved from the GitHub mobile app, though the app shows a list, not
side-by-side columns.

## Findings

### 1. Scopes

- A default `gh auth login` grants `repo`, `read:org`, `gist` and `workflow`. This machine's
  token has exactly those (checked with `gh auth status`, scope names only).
- Projects need their own scopes: `read:project` to read, `project` to read and write. GitHub:
  a token with "the `read:project` scope (for queries)" or "the `project` scope (for queries
  and mutations)". `repo` does not cover projects.
  Source: [Using the API to manage Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects).
- `gh` says the same: `gh project --help` opens with "The minimum required scope for the token
  is: `project`", and suggests `gh auth refresh -s project`.
- Observed: `gh project list --owner @me` with the current token fails with "missing required
  scopes [read:project]".
- Observed, and a trap for the state script: a raw GraphQL query for the user's projects with
  the same token **did not fail**; it returned a count of zero. Without the scope, some queries
  answer "nothing there" instead of an error. The script should check for the scope up front
  (`gh auth status`) rather than trust an empty answer.

### 2. Which token

- **Recommended: add the scope to the existing `gh` login,** once:
  `gh auth refresh -s project`. It opens the browser to approve; the shift then uses the same
  login it already uses for issues. No new token to store.
- **Fine-grained personal access tokens cannot be used.** GitHub lists, among their
  limitations, "Using fine-grained personal access token to access Projects owned by a user
  account." They work only for organisation-owned projects.
  Source: [Managing your personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).
- A classic personal access token with `project` also works, but adds a secret to manage for no
  gain. A GitHub App installation token works for organisation projects; not worth it for a
  solo builder.
- Caveat: `project` is all-or-nothing. It grants write access to every project the account can
  reach, not just the shift's board. GitHub offers no narrower option for user-owned projects.

### 3. What a script can do (all with `project` scope)

The `gh project` commands cover the shift's day-to-day work (`gh project --help`):

| Need | Command |
| --- | --- |
| Add an issue to the board | `gh project item-add <n> --owner @me --url <issue-url>` |
| Move a card to another column | `gh project item-edit --id <item> --project-id <project> --field-id <status-field> --single-select-option-id <option>` |
| Read cards and their columns | `gh project item-list <n> --owner @me --format json` |
| Read field and option ids | `gh project field-list <n> --owner @me --format json` |
| Archive a finished card | `gh project item-archive` |

Points the state script must handle:

- **Moving a card means setting its Status field.** A board's columns are the values of a
  single-select field (Status by default); dragging a card sets that value.
  Source: [Customizing the board layout](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/customizing-the-board-layout).
- **It works by ids, not names.** `item-edit` needs the project's id, the Status field's id and
  the chosen option's id, so the script looks them up once (`field-list`) and keeps them.
- **Add, then move: two calls.** "You cannot add and update an item in the same call."
  Adding an issue that is already on the board returns the existing card rather than a
  duplicate, so adding is safe to repeat. Source: the API page above.
- **One field per call** for real issues (`gh project item-edit --help`).

The one-time setup is scriptable too. The live GraphQL schema has mutations for all of it:
`createProjectV2` (optionally linked to a repo at creation), `linkProjectV2ToRepository`,
`createProjectV2Field`, `updateProjectV2Field` (can replace the Status options; its own
description warns that "provided values overwrite existing options", so existing option ids must
be passed back to keep cards in place), and `createProjectV2View` / `updateProjectV2View` with a
`BOARD_LAYOUT`. `gh` wraps the first three as `gh project create`, `gh project link` and
`gh project field-create`.

### 4. What a script cannot do

- **Switch on the built-in automations.** The schema can read a workflow's `enabled` flag and
  delete one, but has no mutation to create or enable one. They are set in the browser
  (project menu, Workflows).
  Source: [Using the built-in automations](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-built-in-automations).
- Two are on by default for a new project: an issue or pull request closed sets Status to Done,
  and a merged pull request sets Status to Done. A newer default, "Pull request linked to
  issue", sets Status to In progress
  ([changelog, 2025-11-06](https://github.blog/changelog/2025-11-06-improved-onboarding-flow-for-github-projects/)).
  Consequence for the shift: when it closes an issue, GitHub moves the card to Done by itself;
  the state script must expect that, not fight it.
- **Not confirmed:** the exact default Status options on a new project (commonly Todo,
  In Progress, Done). No GitHub doc found states them. The script should read the options by
  name and create or rename the ones it needs, not assume.

### 5. Linking the board to the repo

- A board can be listed on a repo only if both have the same owner: "You can only list projects
  that are owned by the same user or organization that owns the repository." A user-owned board
  and a user-owned repo on the same account qualify.
- Linking makes the board appear in the repo's Projects tab. Visibility is separate: a public
  repo does not make a private board public.
  Source: [Adding your project to a repository](https://docs.github.com/en/issues/planning-and-tracking-with-projects/managing-your-project/adding-your-project-to-a-repository).

### 6. Mobile

- Projects on GitHub Mobile (iOS and Android) has been generally available since March 2023.
  You can switch between a project's views, see each item's fields (such as Status) and "Simply
  tap on the list to edit the fields."
  Source: [Projects on GitHub Mobile is now generally available](https://github.blog/changelog/2023-03-14-projects-on-github-mobile-is-now-generally-available/).
- Since June 2023, projects you work on appear on the app's home screen
  ([changelog](https://github.blog/changelog/2023-06-27-quick-access-to-projects-on-github-mobile/)).
- Limitation: the app draws views as a list grouped by column, not as side-by-side columns
  (beta notes, [2022-10-11](https://github.blog/changelog/2022-10-11-on-the-go-with-github-projects-on-github-mobile-public-beta/));
  no later source says a column board arrived. For a full board on a phone, the mobile browser
  shows the web page.

## The builder's one-time setup

1. Run `gh auth refresh -s project` and approve in the browser. (The only step a script must
   not do for you: it changes your account's login.)
2. Let a setup script create the board, link it to the repo, set the Status options and make a
   board view. Or do it by hand: create a project, add a Board view, link it from the repo's
   Projects tab.
3. In the browser, open the project's Workflows and check the defaults are as wanted (closed
   issue to Done is on by default). Optionally turn on auto-add for the repo.
4. Open the GitHub mobile app once and pin or find the project on the home screen.

## Open points for the state script

- Columns it needs and their names (to be decided with the state script's interface).
- Where it keeps the project, field and option ids between runs.
- Whether it checks for the `project` scope at shift start and refuses or degrades to labels
  only when it is missing.
