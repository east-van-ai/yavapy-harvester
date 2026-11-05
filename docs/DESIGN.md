# YavaPy harvester design

## The question

YavaPy answers one question: which published Python command-line projects have
an Agent Skill in their source repository? It is an existence index. It is not
a marketplace, a review service, or a benchmark.

General skill directories start from GitHub, or from what people submit. Both
populations are huge. PyPI gives a bounded one, with named projects and
declared source links, and it stays small next to GitHub.

Every PyPI project began as a public statement of intent. Many names are
empty lots, registered and never built on. A release in the last twelve months
shows the intent was carried through and is still alive. That is a signal of
seriousness that needs no judgement of quality.

## Scope

- **PyPI only.** Other registries, npm included, are a possible later
  population, not a design input.
- **Console projects.** The `Environment :: Console` classifier marks the
  candidates. It is an imperfect signal for a command-line tool, and it is good
  enough. A command-line tool is the natural home for a skill, because an agent
  can run what the skill describes.
- **Released in the last twelve months.** Older projects stay out.
- **Useful, not complete.** A project whose repository URL is missing or odd
  is simply not found.

## Inclusion

Existence is the admission test. A `SKILL.md` in the declared source
repository qualifies, whatever its quality. A quality gate would need an answer
to "good for which model, which runtime, which task?", and none of those
answers is stable. Leaving quality out keeps the index reproducible, neutral,
and cheap to run.

A listing is a statement of fact, never an endorsement. The site says so.

YavaPy links to a skill and never republishes it. The repository is the source
of truth and keeps its own licence. The directory stores the metadata needed
to search and to link, nothing more.

## Data model

One table, one row per candidate. The columns are listed in the data
repository's README, at <https://github.com/east-van-ai/yavapy-data>. That
README is the reference for the format, for the harvester, the search page,
and anyone else who reads the file. What follows is the reasoning behind it.

The classifiers are the map for widening the search. The ones that projects
with a skill carry say where to look past the console filter.

Misses stay in the table. The table is then a census of candidates as well as
a directory: how many there are, which host each lives on, and how many carry
a skill.

A skill has no record of its own. A skill shared across a monorepo shows as
two rows with the same repository. The count says when a repository holds
more than one `SKILL.md`, and the repository shows the rest. The skill's
frontmatter is not read. Messy files would break the parse, and the PyPI
summary already says what the tool does.

An empty skill count means unchecked, not zero. Only GitHub is checked. A
repository on GitLab, Codeberg, or Bitbucket is still recorded, so the table
shows whether another host would be worth adding.

A stale row is normal for an index. A row says a file was found, not that it
is still there. The check date says when.

## Storage

The table is a CSV, sorted by name, in its own public repository. Each
harvest's diff reads line by line, so the data's history is readable. Anyone
can use the file as is. The harvester writes it, and the search page reads it.
This repository holds no data. The backfill list stays out of the data
repository because it is a to-do list, not data.

The catchup mark sits beside the CSV in a small JSON file. It cannot come from
the table: a run that finds no candidate would leave it where it was, and the
next run would check the same projects again.

## Harvest

The source is PyPI itself. Its JSON Simple index lists every project with a
serial, a counter PyPI raises on each change. Serials only rise, so one number
marks how far a harvest has read.

The index does not say which projects are console. Only a project's own JSON
does, so each project costs one lookup, and most lookups find no candidate.

The three directions are three command words, so the command line always names
the one it runs. A flag would leave one of them an unnamed default.

PyPI changes faster than a capped run reads, and newer finds matter more. So
`walkdown` starts at the top and goes down, newest first. It keeps no mark, because
the table is its stop sign: a row holding the project's serial means a run has
been here. A new release raises the serial, so the project is checked again.

`catchup` climbs from its one mark, oldest first, and jumps a name whose row
already holds that serial. Each project is written together with the mark it
moves, so a stopped run resumes where it stopped.

The two leave holes. When more changes than a run's limit arrive between runs,
`walkdown` never reaches what lies under them. Those wait for `catchup`, or for the
project's next release. Useful, not complete, allows that. `catchup` can repeat
lookups if it climbs into ground `walkdown` covered, since a name that did not
qualify leaves no row. That is accepted, so it has no ceiling.

A backfill run works through a list of names, because a name stays put and a
serial moves. A run first clears every name already in the table, with no lookup,
which a serial could not say. Any other comes off after its row is written, so a stop
between the two repeats one lookup and never loses a name. The list's line count
is the work left, and it only falls.

A serial doubles as a rough date. Serial 32007461, a release of the project Xul,
dates to October 25, 2025. So a project below that floor has not released since,
and the index alone rules it out. The list holds the names above the floor, newest
first, because newer finds matter more. It needs no serials and no index.

The list is a working file, and git's `--skip-worktree` keeps a run's edits out of
`git status`. A missing list is an error, because building one would let a mistyped
path read the whole index and start over.

`update` rechecks one name on demand. The other commands skip a row whose serial
matches, so a project with no new release is otherwise never read again. It takes
a name, not a list, because a shell loop already makes a list, and one name needs
no cap.

A removed project keeps its row, emptied to its name and serial 0. Deleting the
row would not hold, because the project's next release would bring it back. A real
serial is never that low, so the row cannot be mistaken for a checked one. Every
command leaves it alone with no lookup, and `update` refuses it. A separate list of
removed names was the alternative, and it is one more file for every reader to
know about.

A change is what triggers a recheck. A project with no new release has
nothing new to say about its repository, at least not through PyPI. The next
release brings it back for a fresh look.

A candidate's repository is the first code-host URL among its declared
project URLs. One call to GitHub's tree API lists every path, so a `SKILL.md`
in any folder counts. The shortest path is the one recorded, so a skill at
the root wins.

The tree is read at the release tag, not at the default branch. A row then
describes what the release shipped, and a skill added later waits for the
next release, as every other change does. The tag is `v{version}` or the bare
version. Tag names are not standard, so a project tagged any other way, or
not at all, stays unchecked. Falling back to the default branch would mix the
release with whatever came after it.

Topics and the licence describe the repository when it was checked, not the
release, because GitHub has no topics at a tag. One call answers both. The
licence is GitHub's SPDX id, since PyPI's licence fields are free text. Keywords
are PyPI's own string, left as published.

Every run is capped at a few hundred projects. GitHub allows more, but a
steady run near its ceiling looks like abuse. The backfill can be slow,
because older finds matter less.

Each run's result is committed to the data repository, so the data has
history and needs no database server.

## Refusals

YavaPy does not generate, rewrite, or summarize skills. It does not test
whether a skill works, judge its writing, rate model compatibility, rank by
popularity, certify security, or install anything. Each of these is a separate
product with its own costs. Another tool can build any of them on top of the
data.

## Alternatives left out

- **Starting from GitHub code search for `SKILL.md`.** It caps at 1,000
  results. PyPI bounds the population instead.
- **BigQuery's PyPI dataset.** One query would bound a year of candidates, but
  it needs a Google account and a key.
- **Every name in the CSV, with empty cells.** A row means a candidate, and most
  names are not one.
- **A floor on the serial walk, with no list.** It downloads the index on every
  run, and it cannot skip what `catchup` already checked.
- **Marks for `walkdown`, closing a gap from both ends.** It leaves no holes, for
  two more numbers and a meeting point to get right.
- **PyPI's XML-RPC changelog.** PyPI plans to deprecate it.
- **PyPI's RSS feeds.** The newest 100 items cover about eleven minutes, with
  no classifiers.
- **Separate project and skill records.** One row per project carries all the
  site shows.
- **A SQLite file in git.** Git sees a binary blob, so the history does not
  read.

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
