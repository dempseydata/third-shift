# The freezing run

The first recorded run of this eval set freezes it (ticket #33). Its raw output stays out of git:
`evals/results/` is ignored, because the output holds machine paths. This file is the kept
result. The builder fills it in by hand from that run, writing no paths, and commits it.

- Date:
- `claude --version`:
- Command: `uv run --script evals/render && claude plugin eval . --ablation none`
- Notes:

| Case | Runs passed | Needed | Pass |
| --- | --- | --- | --- |
| p1-file-contract | /3 | 2 | |
| p2-name-collision | /3 | 2 | |
| p3-adr-contradiction | /3 | 2 | |
| p4-control | /3 | 3 | |
| p5-human-verified | /3 | 2 | |
| p6-human | /3 | 2 | |
| r1-unmet-criterion | /3 | 2 | |
| v1-missing-evidence | /3 | 2 | |
