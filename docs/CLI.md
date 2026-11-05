# YavaPy harvester command line

```text
yavapy-harvester walkdown DIR [--limit N]
yavapy-harvester catchup DIR [--limit N]
yavapy-harvester backfill DIR FILE [--limit N]
yavapy-harvester update DIR NAME
yavapy-harvester version
```

Paths come right after the command word, then options in any order. No option
abbreviates.

## Bare words

- `yavapy-harvester` alone prints the banner and the full help.
- `yavapy-harvester walkdown`, `catchup`, `backfill`, and `update` alone print the
  command's own page.
- `yavapy-harvester version` and `yavapy-harvester --version` print
  `yavapy-harvester` and the installed version on one line.

Each exits 0.

## walkdown

Checks down from PyPI's current serial, newest first. It stops at the limit, or at
the first name whose row already holds its serial or a newer one. It keeps no
mark, so a run soon after another checks few names. A row with serial 0 means
removed, and the run passes it with no call and no count toward the limit.

## catchup

Checks what rose past the catchup mark, oldest first. A name whose row already
holds its serial or a newer one is jumped, with no call and no count toward the
limit, and so is a row with serial 0. A `marks.json` that is missing, empty, or
`{}` means a first run, which sets the mark to PyPI's current serial and checks
nothing.

## backfill

Works through the names in FILE from the top, one name per line, and reads no
index.

- Every name that already has a row comes off first, with no call, and does not
  count toward the limit. Any other comes off once it is checked.
- An empty FILE means the backfill is finished.
- A missing FILE is an error. The run makes no call and writes nothing.
- With `--limit 0`, the run clears the names with rows and checks nothing.

## update

Checks NAME whatever its row's serial, and the row takes the serial PyPI reports.

- A row with serial 0 means removed, and is refused with no call.
- A project that is no longer a candidate loses its row.
- A failed lookup writes nothing.

It takes no `--limit`.

## All commands

Each records every candidate in `projects.csv` in DIR, whether or not its
repository holds a `SKILL.md`. DIR must exist. A missing CSV reads as empty.

`--limit N` checks at most N projects, on all but `update`. The default is 200.

`GITHUB_TOKEN`, when set, authenticates the GitHub calls. Without it, GitHub
allows 60 an hour.

Each prints one line: the projects checked, the candidates among them, the
candidates with a skill, and where the run got to. `update` prints the version and
the skill files found, or that the project is not a candidate. The line is worded
to serve as the data commit's title, and a failed run prints nothing, so git aborts:

```text
chore: walkdown 40 projects, 1 candidates, 0 with skills, down to 43085133
chore: catchup 5 projects, 0 candidates, 0 with skills, mark 43027309
chore: backfill 5 projects, 1 candidates, 1 with skills, 336406 names left
chore: update abx-dl to 1.13.317, 1 with skills
chore: update some-project, not a candidate
```

## Files

The CSV has one row per candidate, sorted by name. Its columns are listed in
the data repository's README, at <https://github.com/east-van-ai/yavapy-data>.

`marks.json` holds the `catchup` serial.

FILE holds one project name per line.

## Exit codes

| Code | Means |
| --- | --- |
| 0 | success, and documentation |
| 1 | yavapy-harvester's own error, listed below |
| 2 | an unknown command, an unknown option, or a bad value |

Code 1 covers a bad command line, a missing directory or list, a removed row given to
`update`, and a run that could not reach PyPI or GitHub.

A grammar error prints the command's usage line. A run that stops partway
names where it stopped. Its mark or its list is saved, so the next run picks up
there.

## Use of AI

Both the use of AI and its disclosure are deliberate. Code and documentation in
this project are written in collaboration with Artificial Intelligence (AI). The
division of labour: the AI explores, challenges assumptions and edge cases, and
drafts; the human initiates, drafts the designs, explores alongside the AI,
reviews every change, and decides what gets committed.

---

**East Van AI** · AI for the rest of us! · Vancouver, BC, Canada

[github.com/east-van-ai](https://github.com/east-van-ai) · <east-van-ai@proton.me>

Copyright (c) 2026 Go Nakamaru
