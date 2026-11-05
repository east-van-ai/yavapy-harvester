"""
        YavaPy harvester -- Walkdown

https://github.com/east-van-ai/yavapy-harvester

Check down from PyPI's current serial, and record each candidate in a CSV in
DIR, whether or not its repository holds a SKILL.md.

The run takes the newest projects first. It stops at --limit, or at the first
name whose row already holds its serial or a newer one. It keeps no mark, since
the CSV is its stop sign. So a run soon after another checks few names, and what
it did not reach waits for catchup, or for the project's next release. A row with
serial 0 means removed, and the run passes it with no call and no count.

A candidate has the Environment :: Console classifier and a release in the
last 365 days. Its row records the version, the summary, the classifiers,
the release date, when it was checked, and its repository on GitHub, GitLab,
Codeberg, or Bitbucket. Only a GitHub repository is checked, at the tag of
the released version, v{version} and then {version}, for how many SKILL.md
files it holds and the path of one. No matching tag, or another host, leaves
it unchecked. A rechecked project that is no longer a candidate drops out.

A GitHub repository also gives its topics and licence, as they are now. PyPI
gives the keywords.

GITHUB_TOKEN, when set, authenticates the GitHub calls. Without it, GitHub
allows 60 an hour.

The one line printed reports the projects checked, the candidates among them,
the candidates with a skill, and the lowest serial reached. It is worded to serve
as the data commit's title.
"""

import os
import urllib.error
from datetime import UTC, datetime

from yavapy_harvester import data, errors, harvest, shared

HELP = "check down from PyPI's current serial, newest first"
USAGE = "yavapy-harvester walkdown DIR [--limit N]"
SLOTS = ("DIR",)


def walkdown(directory, get, limit=200, token=None, now=None):
    """Check down from PyPI's current serial and record the candidates.

    The run stops at `limit` lookups, or at the first name whose row already
    holds its serial or a newer one. A removed row is passed, with no lookup and
    no count. It keeps no mark, since the CSV is its stop sign. Returns (checked,
    candidates, with skills, lowest serial reached).
    """
    now = now or datetime.now(UTC)
    reached, projects = harvest.read_index(get)
    rows = data.read_rows(directory)

    checked = candidates = with_skills = 0
    for project_serial, name in sorted(projects, reverse=True):
        if harvest.removed(rows, name):
            continue
        if checked >= limit or harvest.matches(rows, name, project_serial):
            break
        try:
            row = harvest.check(get, name, project_serial, token, now)
        except (urllib.error.URLError, TimeoutError) as failure:
            raise errors.RuntimeFailure(
                f"stopped at {name} after {checked} projects; their rows are saved: {failure}"
            ) from failure
        harvest.record(directory, rows, row, name)
        checked += 1
        reached = project_serial
        if row is not None:
            candidates += 1
            with_skills += bool(row["skill_count"])

    return checked, candidates, with_skills, reached


def run(path, parsed):
    """Check down from the top into the data directory at `path` and print a one-line summary."""
    shared.require_directory(path)
    checked, candidates, with_skills, reached = walkdown(path, shared.get, parsed.limit, os.environ.get("GITHUB_TOKEN"))
    print(f"chore: walkdown {checked} projects, {candidates} candidates, {with_skills} with skills, down to {reached}")
