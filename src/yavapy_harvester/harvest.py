"""The work the commands share: read the index, check one project, and write its row."""

import urllib.error

from yavapy_harvester import data, errors, github, pypi


def read_index(get):
    """Return PyPI's index, or raise a readiness error when it cannot be read."""
    try:
        return pypi.index(get)
    except urllib.error.URLError as failure:
        raise errors.ReadinessError(f"could not read the PyPI index: {failure}") from failure


def matches(rows, name, serial):
    """Return whether `name` already has a row holding `serial` or a newer one."""
    row = rows.get(pypi.normalize(name))
    return row is not None and row["serial"] >= serial


def removed(rows, name):
    """Return whether `name` has a row with serial 0, meaning removed."""
    row = rows.get(pypi.normalize(name))
    return row is not None and row["serial"] == 0


def record(directory, rows, row, name):
    """Replace `name`'s row with `row`, or drop it when `row` is None, and write any change."""
    dropped = rows.pop(pypi.normalize(name), None)
    if row is not None:
        rows[row["name"]] = row
    if row is not None or dropped is not None:
        data.write_rows(directory, rows)


def check(get, name, serial, token, now):
    """Return a candidate's row, or None when the project is not a candidate.

    Only a GitHub repository is checked, at the tag of the released version:
    `v{version}`, then `{version}`. Another host, or no matching tag, leaves
    the tag and skill columns empty. Another host also leaves the topics and
    licence empty. With no `serial` given, the row takes the one PyPI reports
    for the project.
    """
    doc = pypi.project(get, name)
    if doc is None:
        return None
    project = pypi.release(doc, now)
    if project is None:
        return None
    repo_url = pypi.repo_url(doc)
    tag = paths = topics = spdx_id = None
    if repo_url and repo_url.startswith("https://github.com/"):
        topics, spdx_id = github.topics_and_license(get, repo_url, token)
        for ref in (f"v{project['version']}", project["version"]):
            paths = github.skill_paths(get, repo_url, ref, token)
            if paths is not None:
                tag = ref
                break
    return project | {
        "serial": doc["last_serial"] if serial is None else serial,
        "checked_at": now.isoformat(timespec="seconds"),
        "repo_url": repo_url,
        "tag": tag,
        "skill_count": None if paths is None else len(paths),
        "skill_path": min(paths, key=lambda path: (len(path), path)) if paths else None,
        "topics": topics,
        "license": spdx_id,
    }
