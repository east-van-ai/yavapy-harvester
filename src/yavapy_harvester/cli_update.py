"""
        YavaPy harvester -- Update

https://github.com/east-van-ai/yavapy-harvester

Check one project again, and record it in a CSV in DIR, whether or not its
repository holds a SKILL.md.

NAME is checked whatever its row's serial, so a project with no new release can
be read again. The row takes the serial PyPI reports. A row with serial 0 means
removed, and it is refused with no call. A project that is no longer a candidate
drops out.

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

The one line printed reports the version and the skill files found, or that the
project is not a candidate. It is worded to serve as the data commit's title.
"""

import os
import urllib.error
from datetime import UTC, datetime

from yavapy_harvester import data, errors, harvest, pypi, shared

HELP = "check one project again, whatever its serial"
USAGE = "yavapy-harvester update DIR NAME"
SLOTS = ("DIR", "NAME")


def update(directory, name, get, token=None, now=None):
    """Check `name` and record it, returning its row, or None when it is not a candidate.

    A removed row is refused with no lookup. A failed lookup is a readiness
    error, since nothing has been written.
    """
    now = now or datetime.now(UTC)
    rows = data.read_rows(directory)
    if harvest.removed(rows, name):
        raise errors.ReadinessError(f"{pypi.normalize(name)} was removed: its row has serial 0")
    try:
        row = harvest.check(get, name, None, token, now)
    except (urllib.error.URLError, TimeoutError) as failure:
        raise errors.ReadinessError(f"could not check {name}: {failure}") from failure
    harvest.record(directory, rows, row, name)
    return row


def run(path, name, parsed):
    """Check one project into the data directory at `path` and print a one-line summary."""
    shared.require_directory(path)
    row = update(path, name, shared.get, os.environ.get("GITHUB_TOKEN"))
    if row is None:
        print(f"chore: update {pypi.normalize(name)}, not a candidate")
    else:
        print(f"chore: update {row['name']} to {row['version']}, {row['skill_count'] or 0} with skills")
