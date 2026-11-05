"""Tests for the topics, license, and keywords columns, from fixture responses into a real data directory."""

import json

from test_harvest import NOW, pypi_doc, skill

from yavapy_harvester import cli_update, data, harvest

REPO = "https://api.github.com/repos/o/tool"


def details(topics=("zebra", "apple"), spdx_id="MIT"):
    """Return a GitHub repository response holding `topics` and a licence."""
    license_ = {"spdx_id": spdx_id} if spdx_id else None
    return json.dumps({"topics": list(topics), "license": license_}).encode()


def with_keywords(doc, keywords):
    """Return a JSON API document with `keywords` set."""
    parsed = json.loads(doc)
    parsed["info"]["keywords"] = keywords
    return json.dumps(parsed).encode()


def serving(bodies):
    """Return a `get` serving `bodies` by URL, a 404 otherwise, and the list of URLs it was asked for."""
    urls = []

    def get(url, headers=None):
        """Serve a fixture body and record the URL."""
        urls.append(url)
        return bodies.get(url)

    return get, urls


def candidate(**extra):
    """Return the bodies for a GitHub candidate called tool, with its tree at v1.0 and a repository response."""
    doc, paths = skill("tool")
    return {
        "https://pypi.org/pypi/tool/json": with_keywords(doc, "scraping, crawling"),
        f"{REPO}/git/trees/v1.0?recursive=1": paths,
        REPO: details(),
    } | extra


def test_a_github_candidate_holds_all_three_columns():
    """Topics are sorted and joined, the licence is the SPDX id, and the keywords are PyPI's own string."""
    get, _ = serving(candidate())
    row = harvest.check(get, "tool", 55, None, NOW)
    assert row["topics"] == "apple; zebra"
    assert row["license"] == "MIT"
    assert row["keywords"] == "scraping, crawling"


def test_no_matching_tag_still_gets_topics_and_a_licence():
    """The columns describe the repository now, so a missing tag does not touch them."""
    bodies = candidate()
    del bodies[f"{REPO}/git/trees/v1.0?recursive=1"]
    get, _ = serving(bodies)
    row = harvest.check(get, "tool", 55, None, NOW)
    assert row["tag"] is None
    assert row["topics"] == "apple; zebra"
    assert row["license"] == "MIT"


def test_a_missing_repository_leaves_both_empty_and_the_row_written(tmp_path):
    """A repository GitHub cannot find empties the two columns, and the candidate keeps its row."""
    get, _ = serving(candidate(**{REPO: None}))
    cli_update.update(tmp_path, "tool", get, now=NOW)
    row = data.read_rows(tmp_path)["tool"]
    assert row["topics"] is None
    assert row["license"] is None
    assert row["keywords"] == "scraping, crawling"


def test_another_host_makes_no_repository_call_and_keeps_its_keywords():
    """Only GitHub has the call, and keywords come from PyPI whatever the host."""
    doc = with_keywords(pypi_doc("tool", repo="https://gitlab.com/o/{name}"), "scraping")
    get, urls = serving({"https://pypi.org/pypi/tool/json": doc})
    row = harvest.check(get, "tool", 55, None, NOW)
    assert urls == ["https://pypi.org/pypi/tool/json"]
    assert row["topics"] is None
    assert row["keywords"] == "scraping"


def test_no_licence_and_no_topics_leave_the_cells_empty(tmp_path):
    """GitHub's null licence and empty topic list both write empty cells."""
    get, _ = serving(candidate(**{REPO: details(topics=(), spdx_id=None)}))
    cli_update.update(tmp_path, "tool", get, now=NOW)
    row = data.read_rows(tmp_path)["tool"]
    assert row["topics"] is None
    assert row["license"] is None


def test_noassertion_is_recorded_as_github_gives_it():
    """Rows record what was found, GitHub's placeholder included."""
    get, _ = serving(candidate(**{REPO: details(spdx_id="NOASSERTION")}))
    assert harvest.check(get, "tool", 55, None, NOW)["license"] == "NOASSERTION"


def test_the_token_reaches_the_repository_call():
    """The new call authenticates as the tree call does."""
    seen = {}
    bodies = candidate()

    def get(url, headers=None):
        """Serve a fixture body and record the repository call's headers."""
        if url == REPO:
            seen.update(headers)
        return bodies.get(url)

    harvest.check(get, "tool", 55, "secret", NOW)
    assert seen["Authorization"] == "Bearer secret"


def test_each_github_candidate_costs_one_repository_call():
    """One call answers both columns."""
    get, urls = serving(candidate())
    harvest.check(get, "tool", 55, None, NOW)
    assert urls.count(REPO) == 1


def test_an_old_row_writes_back_with_empty_cells(tmp_path):
    """A row from the old shape gains the new header and empty cells, and keeps its own."""
    old = "name,serial,version,summary,classifiers,released_at,checked_at,repo_url,tag,skill_count,skill_path\n"
    (tmp_path / "projects.csv").write_text(f"{old}tool,55,1.0,does,,,,,,1,SKILL.md\ngone,0\n")
    data.write_rows(tmp_path, data.read_rows(tmp_path))
    lines = (tmp_path / "projects.csv").read_text().splitlines()
    assert lines[0] == f"{old.strip()},topics,license,keywords"
    assert lines[1] == "gone,0,,,,,,,,,,,,"
    assert lines[2] == "tool,55,1.0,does,,,,,,1,SKILL.md,,,"
