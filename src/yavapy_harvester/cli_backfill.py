"""
        YavaPy harvester -- Backfill

https://github.com/east-van-ai/yavapy-harvester

Work through the backfill list, and record each candidate in a CSV in DIR,
whether or not its repository holds a SKILL.md.

FILE holds one project name per line, and the run takes them from the top. Every
name with a row comes off first, with no call, and does not count toward --limit.
Any other comes off once it is checked, so a stopped run picks up where it left
off. An empty FILE means the backfill is finished, and a missing FILE is an error.
Each run checks at most --limit projects, and --limit 0 only clears the names with
rows.

A candidate has the Environment :: Console classifier and a release in the
last 365 days. Its row records the version, the summary, the classifiers,
the release date, when it was checked, and its repository on GitHub, GitLab,
Codeberg, or Bitbucket. Only a GitHub repository is checked, at the tag of
the released version, v{version} and then {version}, for how many SKILL.md
files it holds and the path of one. No matching tag, or another host, leaves
it unchecked.

A GitHub repository also gives its topics and licence, as they are now. PyPI
gives the keywords.

GITHUB_TOKEN, when set, authenticates the GitHub calls. Without it, GitHub
allows 60 an hour.

The one line printed reports the projects checked, the candidates among them,
the candidates with a skill, and the names left. It is worded to serve as the
data commit's title.
"""

import os
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

from yavapy_harvester import data, errors, harvest, pypi, shared
from yavapy_harvester.errors import ReadinessError

HELP = "work through the backfill list, newest first"
USAGE = "yavapy-harvester backfill DIR FILE [--limit N]"
SLOTS = ("DIR", "FILE")


def backfill(directory, path, get, limit=200, token=None, now=None):
    """Check up to `limit` names from the list at `path` and record the candidates.

    Names that already have a row come off first, with no call. Any other comes
    off after its row is written, so a run stopped between the two repeats one
    lookup and loses nothing. Returns (checked, candidates, with skills, names left).
    """
    now = now or datetime.now(UTC)
    listed = data.read_names(path)
    rows = data.read_rows(directory)
    names = [name for name in listed if pypi.normalize(name) not in rows]
    if len(names) < len(listed):
        data.write_names(path, names)

    checked = candidates = with_skills = 0
    for name in names[:limit]:
        try:
            row = harvest.check(get, name, None, token, now)
        except (urllib.error.URLError, TimeoutError) as failure:
            raise errors.RuntimeFailure(
                f"stopped at {name} after {checked} projects; "
                f"{len(names) - checked} names left in {path}: {failure}"
            ) from failure
        checked += 1
        if row is not None:
            rows[row["name"]] = row
            candidates += 1
            with_skills += bool(row["skill_count"])
            data.write_rows(directory, rows)
        data.write_names(path, names[checked:])

    return checked, candidates, with_skills, len(names) - checked


def run(path, names, parsed):
    """Work through the list at `names` into the data directory at `path` and print a one-line summary."""
    shared.require_directory(path)
    if not Path(names).is_file():
        raise ReadinessError(f"no list at {names}")
    checked, candidates, with_skills, left = backfill(
        path, names, shared.get, parsed.limit, os.environ.get("GITHUB_TOKEN")
    )
    print(f"chore: backfill {checked} projects, {candidates} candidates, {with_skills} with skills, {left} names left")
