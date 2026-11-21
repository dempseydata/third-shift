# The allow and deny rules live in one data file, and the board is found by its title

The allow list and deny rules are one JSON data file in `cli/`. `setup` writes user settings from it and the prescan checks settings against it, so the two cannot drift. The prescan calls the guard active only when the plugin is installed through the plugin route (`enabledPlugins`); the development symlink loads no `hooks.json`.

The board is titled `third-shift: <repo>` and carries a single-select Spec field. The prescan finds it by that title on any Mac; cached ids in runtime state are a speed-up, not the identity.

We considered hard-coding the rules in each consumer (rejected: drift) and identifying the board only by cached ids (rejected: a second Mac could not find it).
