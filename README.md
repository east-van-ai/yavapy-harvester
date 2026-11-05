# YavaPy harvester

The harvest behind YavaPy, Yet Another Virtual Aggregator for PyPI. It finds
the Agent Skills that live beside published Python command-line tools, and
records them in one CSV file.

Some PyPI projects keep a `SKILL.md` in their source repository. It teaches an
agent how to drive the tool: which command, when, and why. An agent could use
it today, but nobody thinks to look there. The harvester looks.

## What gets recorded

A PyPI project is a candidate when it carries the `Environment :: Console`
classifier and published a release in the last twelve months. Every candidate
gets a row, with or without a skill. So the file is a census of candidates as
well as a directory of skills.

The harvester reads the repository at the release's tag, so a row describes
what the release shipped. It points to a skill. It never copies, rewrites, or
summarizes one.

## Running it

The harvester is not on PyPI. It runs with [uv](https://docs.astral.sh/uv/) from
a checkout of this repository, beside a checkout of the data repository:

```bash
git clone https://github.com/east-van-ai/yavapy-harvester ~/yavapy-harvester
```

```bash
git clone https://github.com/east-van-ai/yavapy-data ~/yavapy-data
```

From `~/yavapy-harvester`:

```bash
uv run yavapy-harvester walkdown ~/yavapy-data --limit 200
uv run yavapy-harvester catchup ~/yavapy-data --limit 200
uv run yavapy-harvester backfill ~/yavapy-data names.txt --limit 200
uv run yavapy-harvester update ~/yavapy-data some-project
```

The first path is the data checkout. A run rewrites the CSV in
place. Commit the result to keep the history. Each command prints one line,
written to be the commit's title:

```bash
git commit -am "$(uv run --project ~/yavapy-harvester yavapy-harvester walkdown . --limit 50)"
```

`walkdown` looks at what is newest. It starts at PyPI's latest change and goes
down, stopping at the first project it has already recorded.

`catchup` climbs from where it last stopped, oldest first, and moves its mark in
`marks.json`. A project already recorded is jumped.

`backfill` works through the past. It takes a file of project names, one per
line, newest first, and each name comes off when it is done. So the file's line
count is the work left, and an empty file means the backfill is finished.

`update` checks one project again, by name, even with no new release.

Every run is capped, so it goes gently on PyPI and GitHub. Without a
`GITHUB_TOKEN`, GitHub allows 60 calls an hour, which runs out fast.
`GITHUB_TOKEN=$(gh auth token)` covers a run.

## More documentation

- [CLI](docs/CLI.md): the command line, word by word
- [Design](docs/DESIGN.md): the boundary, the decisions, and the reasons
- [Changelog](CHANGELOG.md): project history and releases

## Use of AI

Code and documentation are written in collaboration with remote and local AI; design
decisions, code review, semantic and auditory review, and final judgement stay human.

---

**East Van AI** · AI for the rest of us! · Vancouver, BC, Canada

[github.com/east-van-ai](https://github.com/east-van-ai) · <east-van-ai@proton.me>

Copyright (c) 2026 Go Nakamaru
