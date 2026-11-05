"""Read a GitHub repository: its topics and licence, and the SKILL.md files at a given ref."""

import json
from urllib.parse import quote


def api_headers(token):
    """Return the headers for a GitHub API call, authenticated when there is a token."""
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def topics_and_license(get, repo_url, token=None):
    """Return a repository's topics, sorted and joined, and its licence's SPDX id.

    One API call answers both, describing the repository now. A missing
    repository, no topics, or no licence gives None in that place.
    """
    owner_repo = repo_url.removeprefix("https://github.com/")
    body = get(f"https://api.github.com/repos/{owner_repo}", api_headers(token))
    if body is None:
        return None, None
    repo = json.loads(body)
    return "; ".join(sorted(repo.get("topics") or [])) or None, (repo.get("license") or {}).get("spdx_id")


def skill_paths(get, repo_url, ref, token=None):
    """Return the path of every SKILL.md in a repository's tree at `ref`.

    One API call reads the whole tree. A missing repository, a missing ref, or
    a truncated tree gives None, meaning the tree could not be checked.
    """
    owner_repo = repo_url.removeprefix("https://github.com/")
    tree_ish = quote(ref, safe="")
    body = get(f"https://api.github.com/repos/{owner_repo}/git/trees/{tree_ish}?recursive=1", api_headers(token))
    if body is None:
        return None
    tree = json.loads(body)
    if tree.get("truncated"):
        return None
    return [
        entry["path"]
        for entry in tree["tree"]
        if entry["type"] == "blob" and (entry["path"] == "SKILL.md" or entry["path"].endswith("/SKILL.md"))
    ]
