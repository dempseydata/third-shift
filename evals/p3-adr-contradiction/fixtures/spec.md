title:	quill version 1
state:	OPEN
author:	example-builder
labels:	
comments:	0
assignees:	
projects:	
milestone:	
number:	10
--
## Problem Statement

People who keep a work journal in a plain text file lose entries and cannot get them into a
spreadsheet.

## Solution

`quill`, a small command-line journal. `quill add <text>` stores an entry with the current time,
`quill list` prints the entries, and `quill export` writes them as CSV to standard output.

## User Stories

1. As a user, I add an entry with one command, so that writing it takes no effort.
2. As a user, I list my entries, so that I can read back what I did.
3. As a user, I export my entries as CSV, so that I can open them in a spreadsheet.

## Implementation Decisions

- The tool is a Node.js command-line program named `quill`, published to npm as `quill-journal`
  and installed with `npm install -g quill-journal`.
- Entries are stored as tab-separated lines, `<time>\t<text>`, in `$QUILL_HOME/journal.tsv` (default `~/.quill`).
- Times are ISO-8601 UTC with seconds precision, such as `2026-03-01T09:30:00Z`.
- Exit codes: 0 success, 1 usage error, 3 journal missing or unreadable. Messages go to standard
  error.
- Sub-issues: #11, #12, #13.

## Testing Decisions

Tests run the built CLI as a subprocess in a temporary `QUILL_HOME`, as `verify/recipe.md` says.
They assert on standard output, standard error, the exit code and the journal file.

## Out of Scope

Sync, encryption, editing or deleting past entries.
