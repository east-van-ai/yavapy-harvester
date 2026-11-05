"""Read PyPI: the JSON Simple index and the per-project JSON API."""

import json
import re
from datetime import datetime, timedelta
from urllib.parse import quote

INDEX_URL = "https://pypi.org/simple/"
INDEX_ACCEPT = "application/vnd.pypi.simple.v1+json"
CONSOLE = "Environment :: Console"
WINDOW = timedelta(days=365)
REPO = re.compile(
    r"^https?://(?:www\.)?(github\.com|gitlab\.com|codeberg\.org|bitbucket\.org)/([\w.-]+)/([\w.-]+)",
    re.IGNORECASE,
)


def normalize(name):
    """Return a project name in PyPI's normalized form."""
    return re.sub(r"[-_.]+", "-", name).lower()


def index(get):
    """Return PyPI's current serial and a (serial, name) pair per project."""
    data = json.loads(get(INDEX_URL, {"Accept": INDEX_ACCEPT}))
    return data["meta"]["_last-serial"], [(p["_last-serial"], p["name"]) for p in data["projects"]]


def project(get, name):
    """Return the JSON API document for `name`, or None when PyPI has none."""
    body = get(f"https://pypi.org/pypi/{quote(name)}/json")
    return None if body is None else json.loads(body)


def release(doc, now):
    """Return a project's record when it passes the filter, else None.

    The filter: the console classifier, and a latest release uploaded within
    the window. A latest release with no files is skipped.
    """
    info = doc["info"]
    classifiers = info.get("classifiers") or []
    if CONSOLE not in classifiers:
        return None
    uploads = [file["upload_time_iso_8601"] for file in doc.get("urls") or []]
    if not uploads:
        return None
    released = max(datetime.fromisoformat(upload) for upload in uploads)
    if now - released > WINDOW:
        return None
    return {
        "name": normalize(info["name"]),
        "summary": info.get("summary") or "",
        "classifiers": "; ".join(sorted(classifiers)),
        "version": info["version"],
        "released_at": released.isoformat(timespec="seconds"),
        "keywords": info.get("keywords") or "",
    }


def repo_url(doc):
    """Return the first code-host repository a project declares, cleaned, or None.

    Project URLs come before the home page. A URL is cut to host, owner, and
    repository, with a trailing `.git` dropped.
    """
    info = doc["info"]
    for url in [*(info.get("project_urls") or {}).values(), info.get("home_page")]:
        match = REPO.match(url or "")
        if match:
            host, owner, repo = match.groups()
            return f"https://{host.lower()}/{owner}/{repo.removesuffix('.git')}"
    return None
