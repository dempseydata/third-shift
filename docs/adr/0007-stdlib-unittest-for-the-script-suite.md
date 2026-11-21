# The scripts' suite is stdlib unittest, driven through a fake gh

Tests for `cli/shift`, `cli/prescan` and the hook entry points live in `tests/`, use the standard library's `unittest`, and run as `uv run python -m unittest`. A fake `gh` at `tests/bin/gh` goes first on the path, serves canned issues, and records every write. Tests run the real commands as subprocesses against temporary repositories with a local bare remote.

We considered pytest, and rejected it: the spec admits a library only for a named need of the script itself, and the suite's needs are met by the standard library.
