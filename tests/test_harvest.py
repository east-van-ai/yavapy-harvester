"""Tests for the harvest, from fixture responses into a real data directory."""

import json
import urllib.error
from datetime import UTC, datetime

import pytest

from yavapy_harvester import cli_backfill, cli_catchup, cli_walkdown, data, errors

NOW = datetime(2026, 10, 30, tzinfo=UTC)


def pypi_doc(name, console=True, uploaded="2026-10-01T12:00:00Z", repo="https://github.com/o/{name}"):
    """Return a JSON API document for a fixture project."""
    classifiers = ["Environment :: Console"] if console else ["Environment :: Web Environment"]
    info = {
        "name": name,
        "version": "1.0",
        "summary": f"{name} does things",
        "classifiers": classifiers,
        "project_urls": {"Source": repo.format(name=name)},
        "home_page": None,
    }
    return json.dumps({"info": info, "last_serial": 55, "urls": [{"upload_time_iso_8601": uploaded}]}).encode()


def tree(*paths):
    """Return a GitHub tree response holding `paths` as blobs."""
    return json.dumps({"truncated": False, "tree": [{"path": p, "type": "blob"} for p in paths]}).encode()


def fake_pypi(serial, projects, tag="v1.0"):
    """Return a `get` serving the index for `projects`, a {name: (serial, json, tree)} map.

    Each tree sits at `tag`. Any other URL, and any None body, is a 404.
    """
    index = {
        "meta": {"_last-serial": serial},
        "projects": [{"name": name, "_last-serial": s} for name, (s, _, _) in projects.items()],
    }
    bodies = {"https://pypi.org/simple/": json.dumps(index).encode()}
    for name, (_, doc, paths) in projects.items():
        bodies[f"https://pypi.org/pypi/{name}/json"] = doc
        bodies[f"https://api.github.com/repos/o/{name}/git/trees/{tag}?recursive=1"] = paths

    def get(url, headers=None):
        """Serve a fixture body."""
        return bodies.get(url)

    return get


def skill(name, *paths):
    """Return a candidate whose GitHub tree holds `paths`, SKILL.md at the root by default."""
    return pypi_doc(name), tree("README.md", *(paths or ("SKILL.md",)))


def rows(directory):
    """Return the stored rows."""
    return data.read_rows(directory)


def start(directory, serial=100):
    """Run once on an empty directory, setting the catchup mark to `serial`."""
    cli_catchup.catchup(directory, fake_pypi(serial, {}), now=NOW)


def test_first_run_sets_the_mark_and_checks_nothing(tmp_path):
    """An empty directory starts the catchup mark at the index's serial."""
    get = fake_pypi(100, {"a": (90, *skill("a"))})
    assert cli_catchup.catchup(tmp_path, get, now=NOW) == (0, 0, 0, 100)
    assert data.read_marks(tmp_path) == {"catchup": 100}
    assert rows(tmp_path) == {}


def test_brace_marks_file_is_a_first_run(tmp_path):
    """A marks.json holding `{}` starts the catchup mark at the index's serial."""
    (tmp_path / data.MARKS).write_text("{}\n")
    assert cli_catchup.catchup(tmp_path, fake_pypi(100, {}), now=NOW) == (0, 0, 0, 100)
    assert data.read_marks(tmp_path) == {"catchup": 100}


def test_catchup_run_catches_up_to_the_index(tmp_path):
    """Projects past the catchup mark are checked, then the mark meets the index."""
    start(tmp_path)
    get = fake_pypi(120, {"old": (50, *skill("old")), "new": (110, *skill("new"))})
    assert cli_catchup.catchup(tmp_path, get, now=NOW) == (1, 1, 1, 120)
    assert sorted(rows(tmp_path)) == ["new"]
    assert data.read_marks(tmp_path) == {"catchup": 120}


def test_a_run_with_no_candidates_still_moves_its_mark(tmp_path):
    """Non-candidates leave no row, but the next run does not check them again."""
    start(tmp_path)
    web = (pypi_doc("w1", console=False), None)
    get = fake_pypi(130, {"w1": (110, *web), "w2": (120, *web), "c": (125, *skill("c"))})
    assert cli_catchup.catchup(tmp_path, get, limit=2, now=NOW) == (2, 0, 0, 120)
    assert cli_catchup.catchup(tmp_path, get, limit=2, now=NOW) == (1, 1, 1, 130)


def test_row_holds_every_column(tmp_path):
    """A candidate's row carries its release, its repository, and its skills."""
    start(tmp_path)
    cli_catchup.catchup(tmp_path, fake_pypi(110, {"t": (105, *skill("t", "skills/b/SKILL.md", "SKILL.md"))}), now=NOW)
    assert rows(tmp_path)["t"] == {
        "name": "t",
        "serial": 105,
        "version": "1.0",
        "summary": "t does things",
        "classifiers": "Environment :: Console",
        "released_at": "2026-10-01T12:00:00+00:00",
        "checked_at": "2026-10-30T00:00:00+00:00",
        "repo_url": "https://github.com/o/t",
        "tag": "v1.0",
        "skill_count": 2,
        "skill_path": "SKILL.md",
        "topics": None,
        "license": None,
        "keywords": None,
    }


def test_bare_version_tag_is_tried_second(tmp_path):
    """A repository tagged `1.0` instead of `v1.0` is still checked."""
    start(tmp_path)
    cli_catchup.catchup(tmp_path, fake_pypi(110, {"t": (105, *skill("t"))}, tag="1.0"), now=NOW)
    row = rows(tmp_path)["t"]
    assert (row["tag"], row["skill_count"]) == ("1.0", 1)


def test_no_matching_tag_leaves_the_row_unchecked(tmp_path):
    """Without a release tag there is no fallback to HEAD."""
    start(tmp_path)
    cli_catchup.catchup(tmp_path, fake_pypi(110, {"t": (105, *skill("t"))}, tag="release-1.0"), now=NOW)
    row = rows(tmp_path)["t"]
    assert (row["tag"], row["skill_count"], row["skill_path"]) == (None, None, None)


def test_misses_are_kept_and_non_candidates_are_not(tmp_path):
    """Candidates without a skill get a row; old or non-console projects do not."""
    start(tmp_path)
    projects = {
        "plain": (101, pypi_doc("plain"), tree("README.md")),
        "nohost": (102, pypi_doc("nohost", repo="https://example.com/{name}"), None),
        "gitlab": (103, pypi_doc("gitlab", repo="https://gitlab.com/o/{name}"), None),
        "deadrepo": (104, pypi_doc("deadrepo"), None),
        "web": (105, pypi_doc("web", console=False), None),
        "stale": (106, pypi_doc("stale", uploaded="2025-01-01T00:00:00Z"), None),
        "gone": (107, None, None),
    }
    assert cli_catchup.catchup(tmp_path, fake_pypi(110, projects), now=NOW) == (7, 4, 0, 110)
    found = {name: (r["repo_url"], r["skill_count"]) for name, r in rows(tmp_path).items()}
    assert found == {
        "plain": ("https://github.com/o/plain", 0),
        "nohost": (None, None),
        "gitlab": ("https://gitlab.com/o/gitlab", None),
        "deadrepo": ("https://github.com/o/deadrepo", None),
    }


def test_recheck_drops_a_project_that_is_no_longer_a_candidate(tmp_path):
    """A project that loses the console classifier leaves the file."""
    start(tmp_path)
    cli_catchup.catchup(tmp_path, fake_pypi(110, {"t": (105, *skill("t"))}), now=NOW)
    assert sorted(rows(tmp_path)) == ["t"]
    cli_catchup.catchup(tmp_path, fake_pypi(120, {"t": (115, pypi_doc("t", console=False), None)}), now=NOW)
    assert rows(tmp_path) == {}


def test_network_failure_stops_the_run_with_the_mark_saved(tmp_path):
    """A failure midway raises, and the projects already checked stay recorded."""
    start(tmp_path)
    good = fake_pypi(130, {"a": (110, *skill("a")), "b": (120, *skill("b"))})

    def get(url, headers=None):
        """Fail on project b, serve everything else."""
        if url.endswith("/b/json"):
            raise urllib.error.URLError("rate limited")
        return good(url, headers)

    with pytest.raises(errors.RuntimeFailure, match=r"stopped at b after 1 projects.*saved at 110"):
        cli_catchup.catchup(tmp_path, get, now=NOW)
    assert sorted(rows(tmp_path)) == ["a"]
    assert data.read_marks(tmp_path)["catchup"] == 110


def test_unreachable_index_is_a_readiness_error(tmp_path):
    """Nothing is written when the index cannot be read."""

    def get(url, headers=None):
        """Fail every request."""
        raise urllib.error.URLError("offline")

    with pytest.raises(errors.ReadinessError, match="could not read the PyPI index"):
        cli_catchup.catchup(tmp_path, get, now=NOW)
    assert list(tmp_path.iterdir()) == []


def names_file(tmp_path, *names):
    """Write a backfill list outside the data directory and return its path."""
    path = tmp_path / "backfill.txt"
    data.write_names(path, names)
    return path


def no_index(projects):
    """Return a `get` for `projects` that fails the test if it reads the index."""
    good = fake_pypi(100, projects)

    def get(url, headers=None):
        """Serve a fixture body, but never the index."""
        assert url != "https://pypi.org/simple/"
        return good(url, headers)

    return get


def test_backfill_takes_names_from_the_top_with_no_index_call(tmp_path):
    """Two of three names are checked, in file order, and come off the list."""
    path = names_file(tmp_path, "c", "b", "a")
    get = no_index({"a": (70, *skill("a")), "b": (80, *skill("b")), "c": (90, *skill("c"))})
    assert cli_backfill.backfill(tmp_path, path, get, limit=2, now=NOW) == (2, 2, 2, 1)
    assert sorted(rows(tmp_path)) == ["b", "c"]
    assert data.read_names(path) == ["a"]


def test_row_takes_pypis_serial_on_a_backfill(tmp_path):
    """A backfill has no index, so the serial comes from the project's document."""
    path = names_file(tmp_path, "a")
    cli_backfill.backfill(tmp_path, path, no_index({"a": (70, *skill("a"))}), now=NOW)
    assert rows(tmp_path)["a"]["serial"] == 55


def test_a_name_with_a_row_comes_off_with_no_call_and_does_not_count(tmp_path):
    """The row stays as it was, and the limit counts lookups only."""
    cli_backfill.backfill(tmp_path, names_file(tmp_path, "a"), no_index({"a": (70, *skill("a"))}), now=NOW)
    before = rows(tmp_path)["a"]
    path = names_file(tmp_path, "A", "b", "c")
    calls = []
    good = no_index({"b": (80, *skill("b")), "c": (90, *skill("c"))})

    def get(url, headers=None):
        """Note each PyPI lookup, then serve it."""
        if "pypi.org" in url:
            calls.append(url)
        return good(url, headers)

    assert cli_backfill.backfill(tmp_path, path, get, limit=1, now=NOW) == (1, 1, 1, 1)
    assert calls == ["https://pypi.org/pypi/b/json"]
    assert rows(tmp_path)["a"] == before
    assert data.read_names(path) == ["c"]


def test_limit_zero_clears_names_with_rows_from_anywhere_with_no_call(tmp_path):
    """The first pass reaches the whole list, and nothing is checked."""
    cli_backfill.backfill(tmp_path, names_file(tmp_path, "a"), no_index({"a": (70, *skill("a"))}), now=NOW)
    path = names_file(tmp_path, "b", "a", "c")
    assert cli_backfill.backfill(tmp_path, path, no_index({}), limit=0, now=NOW) == (0, 0, 0, 2)
    assert data.read_names(path) == ["b", "c"]


def test_a_name_with_a_row_past_the_limit_comes_off_too(tmp_path):
    """The names left are only the unchecked ones, however the limit falls."""
    cli_backfill.backfill(tmp_path, names_file(tmp_path, "a"), no_index({"a": (70, *skill("a"))}), now=NOW)
    path = names_file(tmp_path, "b", "c", "a")
    get = no_index({"b": (80, *skill("b")), "c": (90, *skill("c"))})
    assert cli_backfill.backfill(tmp_path, path, get, limit=1, now=NOW) == (1, 1, 1, 1)
    assert data.read_names(path) == ["c"]


def test_a_list_with_nothing_to_clear_is_not_rewritten(tmp_path, monkeypatch):
    """A run that checks nothing and clears nothing leaves the file alone."""
    path = names_file(tmp_path, "a", "b")
    monkeypatch.setattr(data, "write_names", lambda *args: pytest.fail("list rewritten"))
    assert cli_backfill.backfill(tmp_path, path, no_index({}), limit=0, now=NOW) == (0, 0, 0, 2)


def test_trailing_names_with_rows_come_off_at_the_end(tmp_path):
    """A list holding only names with rows empties with no call."""
    cli_backfill.backfill(tmp_path, names_file(tmp_path, "a"), no_index({"a": (70, *skill("a"))}), now=NOW)
    path = names_file(tmp_path, "a")
    assert cli_backfill.backfill(tmp_path, path, no_index({}), now=NOW) == (0, 0, 0, 0)
    assert data.read_names(path) == []


def test_non_candidate_comes_off_and_leaves_no_row(tmp_path):
    """A non-console name is done once it is looked up."""
    path = names_file(tmp_path, "web")
    get = no_index({"web": (70, pypi_doc("web", console=False), None)})
    assert cli_backfill.backfill(tmp_path, path, get, now=NOW) == (1, 0, 0, 0)
    assert rows(tmp_path) == {}
    assert data.read_names(path) == []


def test_network_failure_keeps_the_name_and_the_rows_before_it(tmp_path):
    """The failing name stays on the list, and the next run picks up there."""
    path = names_file(tmp_path, "a", "b", "c")
    good = no_index({"a": (70, *skill("a")), "b": (80, *skill("b")), "c": (90, *skill("c"))})

    def get(url, headers=None):
        """Fail on project b, serve everything else."""
        if url.endswith("/b/json"):
            raise urllib.error.URLError("rate limited")
        return good(url, headers)

    with pytest.raises(errors.RuntimeFailure, match=r"stopped at b after 1 projects; 2 names left"):
        cli_backfill.backfill(tmp_path, path, get, now=NOW)
    assert sorted(rows(tmp_path)) == ["a"]
    assert data.read_names(path) == ["b", "c"]
    assert cli_backfill.backfill(tmp_path, path, good, now=NOW) == (2, 2, 2, 0)
    assert sorted(rows(tmp_path)) == ["a", "b", "c"]


def test_stop_between_the_row_and_the_list_repeats_one_lookup(tmp_path, monkeypatch):
    """The row is written first, so a stop there loses no name, and the name is skipped next time."""
    path = names_file(tmp_path, "a", "b")
    get = no_index({"a": (70, *skill("a")), "b": (80, *skill("b"))})
    real = data.write_names

    def stop(*args):
        """Stop the run at the list's first write."""
        raise KeyboardInterrupt

    monkeypatch.setattr(data, "write_names", stop)
    with pytest.raises(KeyboardInterrupt):
        cli_backfill.backfill(tmp_path, path, get, now=NOW)
    monkeypatch.setattr(data, "write_names", real)
    assert sorted(rows(tmp_path)) == ["a"]
    assert data.read_names(path) == ["a", "b"]
    assert cli_backfill.backfill(tmp_path, path, get, now=NOW) == (1, 1, 1, 0)


def test_empty_list_reports_zero_and_makes_no_call(tmp_path):
    """An empty file means finished, and it is not rebuilt."""
    path = names_file(tmp_path)

    def get(url, headers=None):
        """Fail the test on any call."""
        pytest.fail(f"called {url}")

    assert cli_backfill.backfill(tmp_path, path, get, now=NOW) == (0, 0, 0, 0)
    assert path.exists()


def row_at(name, serial):
    """Return a stored row for `name` at `serial`."""
    return {column: None for column in data.COLUMNS} | {"name": name, "serial": serial}


def lookups(projects, serial=100):
    """Return a `get` for `projects` and the list of PyPI lookups it notes."""
    good = fake_pypi(serial, projects)
    seen = []

    def get(url, headers=None):
        """Note each project lookup, then serve it."""
        if url.endswith("/json"):
            seen.append(url.removeprefix("https://pypi.org/pypi/").removesuffix("/json"))
        return good(url, headers)

    return get, seen


def test_walkdown_takes_the_newest_first_and_stops_at_the_limit(tmp_path):
    """Two of three projects are checked, the newest first, and the lowest reached is reported."""
    get, seen = lookups({"a": (70, *skill("a")), "b": (80, *skill("b")), "c": (90, *skill("c"))})
    assert cli_walkdown.walkdown(tmp_path, get, limit=2, now=NOW) == (2, 2, 2, 80)
    assert seen == ["c", "b"]
    assert sorted(rows(tmp_path)) == ["b", "c"]


def test_walkdown_stops_at_the_first_matching_row(tmp_path):
    """A row at the index's serial stops the run, and nothing below it is looked up."""
    data.write_rows(tmp_path, {"b": row_at("b", 80)})
    get, seen = lookups({"a": (70, *skill("a")), "b": (80, *skill("b")), "c": (90, *skill("c"))})
    assert cli_walkdown.walkdown(tmp_path, get, now=NOW) == (1, 1, 1, 90)
    assert seen == ["c"]
    assert "a" not in rows(tmp_path)


def test_walkdown_rechecks_a_row_with_an_older_serial(tmp_path):
    """A new release breaks the match, so the row is replaced and the run goes on."""
    data.write_rows(tmp_path, {"b": row_at("b", 50)})
    get, seen = lookups({"a": (70, *skill("a")), "b": (80, *skill("b"))})
    assert cli_walkdown.walkdown(tmp_path, get, now=NOW) == (2, 2, 2, 70)
    assert seen == ["b", "a"]
    assert rows(tmp_path)["b"]["serial"] == 80


def test_walkdown_drops_a_project_that_no_longer_qualifies(tmp_path):
    """A rechecked project that is no longer a candidate leaves the file."""
    data.write_rows(tmp_path, {"b": row_at("b", 50)})
    get, _ = lookups({"b": (80, pypi_doc("b", console=False), None)})
    assert cli_walkdown.walkdown(tmp_path, get, now=NOW) == (1, 0, 0, 80)
    assert rows(tmp_path) == {}


def test_walkdown_writes_no_mark_and_leaves_catchups_alone(tmp_path):
    """No marks appear from nothing, and existing ones stay as they were."""
    get, _ = lookups({"a": (70, *skill("a"))})
    cli_walkdown.walkdown(tmp_path, get, now=NOW)
    assert not (tmp_path / data.MARKS).exists()
    data.write_marks(tmp_path, {"catchup": 40})
    get, _ = lookups({"b": (75, *skill("b"))})
    cli_walkdown.walkdown(tmp_path, get, now=NOW)
    assert data.read_marks(tmp_path) == {"catchup": 40}


def test_walkdown_rerun_repeats_only_what_sits_above_the_newest_row(tmp_path):
    """A name above the first row left no row, so a rerun looks it up, then stops."""
    projects = {"a": (70, *skill("a")), "web": (90, pypi_doc("web", console=False), None)}
    get, seen = lookups(projects)
    assert cli_walkdown.walkdown(tmp_path, get, now=NOW) == (2, 1, 1, 70)
    assert cli_walkdown.walkdown(tmp_path, get, now=NOW) == (1, 0, 0, 90)
    assert seen == ["web", "a", "web"]


def test_walkdown_network_failure_keeps_the_rows_so_far(tmp_path):
    """A failure midway raises, and the projects already checked stay recorded."""
    good = fake_pypi(100, {"a": (70, *skill("a")), "b": (90, *skill("b"))})

    def get(url, headers=None):
        """Fail on project a, serve everything else."""
        if url.endswith("/a/json"):
            raise urllib.error.URLError("rate limited")
        return good(url, headers)

    with pytest.raises(errors.RuntimeFailure, match=r"stopped at a after 1 projects; their rows are saved"):
        cli_walkdown.walkdown(tmp_path, get, now=NOW)
    assert sorted(rows(tmp_path)) == ["b"]


def test_catchup_jumps_a_matching_row_with_no_lookup_and_no_count(tmp_path):
    """The mark passes the row, and the limit counts lookups only."""
    start(tmp_path, 60)
    data.write_rows(tmp_path, {"a": row_at("a", 70)})
    get, seen = lookups({"a": (70, *skill("a")), "b": (80, *skill("b")), "c": (90, *skill("c"))})
    assert cli_catchup.catchup(tmp_path, get, limit=1, now=NOW) == (1, 1, 1, 80)
    assert seen == ["b"]
    assert data.read_marks(tmp_path) == {"catchup": 80}


def test_catchup_looks_up_a_row_with_an_older_serial(tmp_path):
    """A row older than the index's serial is rechecked and replaced."""
    start(tmp_path, 60)
    data.write_rows(tmp_path, {"a": row_at("a", 50)})
    get, seen = lookups({"a": (70, *skill("a"))})
    assert cli_catchup.catchup(tmp_path, get, now=NOW) == (1, 1, 1, 100)
    assert seen == ["a"]
    assert rows(tmp_path)["a"]["serial"] == 70


def test_catchup_that_clears_everything_then_checks_nothing(tmp_path):
    """The mark meets the index, and the next run has nothing to look up."""
    start(tmp_path, 60)
    get, seen = lookups({"a": (70, *skill("a"))})
    assert cli_catchup.catchup(tmp_path, get, now=NOW)[3] == 100
    assert cli_catchup.catchup(tmp_path, get, now=NOW) == (0, 0, 0, 100)
    assert seen == ["a"]


def test_old_forward_mark_keeps_its_place(tmp_path):
    """An old `forward` key is where catchup starts, and the next write saves `catchup`."""
    (tmp_path / data.MARKS).write_text('{"forward": 60}\n')
    get, seen = lookups({"old": (50, *skill("old")), "new": (70, *skill("new"))})
    cli_catchup.catchup(tmp_path, get, now=NOW)
    assert seen == ["new"]
    assert '"forward"' not in (tmp_path / data.MARKS).read_text()
    assert data.read_marks(tmp_path) == {"catchup": 100}
