"""
        YavaPy harvester -- Catchup

https://github.com/east-van-ai/yavapy-harvester

Climb from the catchup mark, and record each candidate in a CSV in DIR, whether
or not its repository holds a SKILL.md.

The run checks the projects whose serial rose past the catchup mark in DIR's
marks.json, oldest first, and saves the mark as it goes, so a stopped run picks
up where it left off. A name whose row already holds its serial or a newer one
is jumped, with no call and no count toward --limit, and so is a row with serial
0, which means removed. The first run in an empty DIR sets the mark to
PyPI's current serial and checks nothing. Each run checks at most --limit projects.

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
the candidates with a skill, and where the catchup mark stands. It is worded to
serve as the data commit's title.
"""

import os
import urllib.error
from datetime import UTC, datetime

from yavapy_harvester import data, errors, harvest, shared

HELP = "climb from the catchup mark, oldest first"
USAGE = "yavapy-harvester catchup DIR [--limit N]"
SLOTS = ("DIR",)


def catchup(directory, get, limit=200, token=None, now=None):
    """Check up to `limit` projects past the catchup mark and record the candidates.

    A name whose row already holds its serial or a newer one is jumped, with no
    lookup and no count, and so is a removed row. Returns
    (checked, candidates, with skills, mark serial). Each project is written with
    the mark it moves, so a run that stops partway resumes where it stopped.
    """
    now = now or datetime.now(UTC)
    serial, projects = harvest.read_index(get)

    rows = data.read_rows(directory)
    marks = data.read_marks(directory)
    if not marks:
        marks = {"catchup": serial}
        data.write_marks(directory, marks)

    checked = candidates = with_skills = 0
    for project_serial, name in sorted(p for p in projects if p[0] > marks["catchup"]):
        if checked >= limit:
            break
        if not harvest.matches(rows, name, project_serial) and not harvest.removed(rows, name):
            try:
                row = harvest.check(get, name, project_serial, token, now)
            except (urllib.error.URLError, TimeoutError) as failure:
                raise errors.RuntimeFailure(
                    f"stopped at {name} after {checked} projects; "
                    f"the catchup mark is saved at {marks['catchup']}: {failure}"
                ) from failure
            harvest.record(directory, rows, row, name)
            checked += 1
            if row is not None:
                candidates += 1
                with_skills += bool(row["skill_count"])
        marks["catchup"] = project_serial
        data.write_marks(directory, marks)
    else:
        # A run that cleared everything catches up to the index itself.
        marks["catchup"] = serial
        data.write_marks(directory, marks)

    return checked, candidates, with_skills, marks["catchup"]


def run(path, parsed):
    """Climb from the catchup mark into the data directory at `path` and print a one-line summary."""
    shared.require_directory(path)
    checked, candidates, with_skills, serial = catchup(path, shared.get, parsed.limit, os.environ.get("GITHUB_TOKEN"))
    print(f"chore: catchup {checked} projects, {candidates} candidates, {with_skills} with skills, mark {serial}")
