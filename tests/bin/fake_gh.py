"""Fake gh for the script suite (ADR 0007), run by tests/bin/gh.

Reads canned answers from $FAKE_GH_DIR/fixture.json:
  {"repo": "owner/name", "api": {"<api path>": <json>, ...}}
Serves GET `gh api <path>` (with `--jq .[]`
printing one compact element per line, as real gh does). Every other call is a write:
it is appended to $FAKE_GH_DIR/writes.jsonl as its argument list and succeeds silently.
"""
import json
import os
import sys

root = os.environ["FAKE_GH_DIR"]
args = sys.argv[1:]
with open(os.path.join(root, "fixture.json")) as f:
    fixture = json.load(f)

is_get = (
    args[:1] == ["api"]
    and not {"-X", "--method", "-f", "-F", "--field", "--raw-field", "--input"} & set(args)
)
if is_get:
    path = next(a for a in args[1:] if not a.startswith("-") and a != ".[]")
    if path not in fixture["api"]:
        print(f"gh: Not Found (HTTP 404) {path}", file=sys.stderr)
        sys.exit(1)
    body = fixture["api"][path]
    if "--jq" in args and args[args.index("--jq") + 1] == ".[]":
        for item in body:
            print(json.dumps(item))
    else:
        print(json.dumps(body))
    sys.exit(0)

with open(os.path.join(root, "writes.jsonl"), "a") as f:
    f.write(json.dumps(args) + "\n")
