"""Fake gh for the script suite (ADR 0007), run by tests/bin/gh.

Reads canned answers from $FAKE_GH_DIR/fixture.json:
  {"repo": "owner/name", "api": {"<api path>": <json>, ...},
   "graphql": {"<operation name>": <data>, ...}, "post": {"<api path>": <json>, ...},
   "fail": ["<operation name or api path>", ...]}
Serves GET `gh api <path>` (with `--jq .[]`
printing one compact element per line, as real gh does), and `gh api graphql` by the
operation's name, as {"data": ...} ({} if not canned). A graphql query is a read; every other
call is a write: it is appended to $FAKE_GH_DIR/writes.jsonl as its argument list and prints its
canned "graphql" or "post" answer, or nothing. A call named in "fail", or a document whose
braces do not balance, fails unrecorded.
"""
import json
import os
import re
import sys

root = os.environ["FAKE_GH_DIR"]
args = sys.argv[1:]
with open(os.path.join(root, "fixture.json")) as f:
    fixture = json.load(f)


def fail(what):
    print(f"gh: HTTP 502: {what} failed", file=sys.stderr)
    sys.exit(1)


if args[:2] == ["api", "graphql"]:
    query = next(a[6:] for a in args if a.startswith("query="))
    kind, name = re.match(r"\s*(query|mutation)\s+(\w+)", query).groups()
    if query.count("{") != query.count("}"):  # GitHub's parser would refuse it
        fail(f"{name}: unbalanced braces")
    if name in fixture.get("fail", ()):
        fail(name)
    if kind == "mutation":
        with open(os.path.join(root, "writes.jsonl"), "a") as f:
            f.write(json.dumps(args) + "\n")
    print(json.dumps({"data": fixture.get("graphql", {}).get(name, {})}))
    sys.exit(0)

is_get = (
    args[:1] == ["api"]
    and not {"-X", "--method", "-f", "-F", "--field", "--raw-field", "--input"} & set(args)
)
path = next((a for a in args[1:] if not a.startswith("-") and a != ".[]"), None)
if is_get:
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

if path in fixture.get("fail", ()):
    fail(path)
with open(os.path.join(root, "writes.jsonl"), "a") as f:
    f.write(json.dumps(args) + "\n")
if args[:1] == ["api"] and path in fixture.get("post", {}):
    print(json.dumps(fixture["post"][path]))
