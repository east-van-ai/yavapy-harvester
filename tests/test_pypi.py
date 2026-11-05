"""Tests for picking a project's repository."""

from yavapy_harvester import pypi


def doc(project_urls=None, home_page=None):
    """Return a JSON API document holding only URLs."""
    return {"info": {"project_urls": project_urls, "home_page": home_page}}


def test_first_code_host_wins_and_is_cleaned():
    """Non-host URLs are passed over, and `.git` and deeper paths are cut."""
    urls = {"Docs": "https://example.com", "Source": "https://GitHub.com/o/r.git/tree/main"}
    assert pypi.repo_url(doc(urls, "https://github.com/x/y")) == "https://github.com/o/r"


def test_other_hosts_are_kept():
    """GitLab, Codeberg, and Bitbucket count as repositories."""
    assert pypi.repo_url(doc({"Code": "https://gitlab.com/o/r"})) == "https://gitlab.com/o/r"
    assert pypi.repo_url(doc(None, "https://codeberg.org/o/r")) == "https://codeberg.org/o/r"


def test_no_code_host_gives_none():
    """A project with only a website has no repository."""
    assert pypi.repo_url(doc({"Home": "https://example.com"}, None)) is None
