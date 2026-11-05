"""Tests for the update command, from fixture responses into a real data directory."""

import urllib.error

import pytest
from test_harvest import NOW, fake_pypi, pypi_doc, skill

from yavapy_harvester import cli, cli_update, data, errors, shared


def row(name, serial):
    """Return a stored row for `name`, empty past its version."""
    return {column: None for column in data.COLUMNS} | {"name": name, "serial": serial, "version": "0.1"}


def stored(directory, **rows):
    """Write `rows`, a {name: serial} map, as the CSV."""
    data.write_rows(directory, {name: row(name, serial) for name, serial in rows.items()})


def no_call(url, headers=None):
    """Fail the test on any lookup."""
    pytest.fail(f"unexpected call: {url}")


def test_update_replaces_the_row_with_pypis_serial(tmp_path):
    """The row is rechecked, whatever its serial was, and takes the serial PyPI reports."""
    stored(tmp_path, tool=10)
    result = cli_update.update(tmp_path, "tool", fake_pypi(100, {"tool": (55, *skill("tool"))}), now=NOW)
    assert result["version"] == "1.0"
    rows = data.read_rows(tmp_path)
    assert rows["tool"]["serial"] == 55
    assert rows["tool"]["skill_count"] == 1


def test_update_rechecks_a_row_whose_serial_matches(tmp_path):
    """A matching serial stops the bulk commands, and is the reason update exists."""
    stored(tmp_path, tool=55)
    cli_update.update(tmp_path, "tool", fake_pypi(100, {"tool": (55, *skill("tool"))}), now=NOW)
    assert data.read_rows(tmp_path)["tool"]["version"] == "1.0"


def test_update_finds_a_row_by_its_normalized_name(tmp_path):
    """A name spelled another way replaces the row, and leaves no second one."""
    stored(tmp_path, **{"my-tool": 10})
    get = fake_pypi(100, {"My_Tool": (55, pypi_doc("My_Tool", repo="https://example.com/x"), None)})
    cli_update.update(tmp_path, "My_Tool", get, now=NOW)
    rows = data.read_rows(tmp_path)
    assert sorted(rows) == ["my-tool"]
    assert rows["my-tool"]["serial"] == 55


def test_update_refuses_a_removed_row_with_no_call(tmp_path):
    """Serial 0 is a readiness error, and the row stays as it was."""
    stored(tmp_path, gone=0)
    with pytest.raises(errors.ReadinessError, match="gone was removed"):
        cli_update.update(tmp_path, "gone", no_call, now=NOW)
    assert data.read_rows(tmp_path)["gone"]["serial"] == 0


def test_update_refuses_a_removed_row_spelled_another_way(tmp_path):
    """The refusal goes by the normalized name."""
    stored(tmp_path, **{"gone-away": 0})
    with pytest.raises(errors.ReadinessError, match="gone-away was removed"):
        cli_update.update(tmp_path, "Gone_Away", no_call, now=NOW)


def test_update_drops_a_row_no_longer_a_candidate(tmp_path):
    """A project that fails the filter loses its row, as in the bulk commands."""
    stored(tmp_path, tool=10, other=20)
    get = fake_pypi(100, {"tool": (55, pypi_doc("tool", console=False), None)})
    assert cli_update.update(tmp_path, "tool", get, now=NOW) is None
    assert sorted(data.read_rows(tmp_path)) == ["other"]


def test_update_of_a_new_non_candidate_writes_nothing(tmp_path):
    """No row and no candidate leaves no file behind."""
    get = fake_pypi(100, {"tool": (55, pypi_doc("tool", console=False), None)})
    assert cli_update.update(tmp_path, "tool", get, now=NOW) is None
    assert not (tmp_path / data.PROJECTS).exists()


def test_a_failed_lookup_is_a_readiness_error(tmp_path):
    """Nothing is written yet, so the failure is readiness, and the row stays."""
    stored(tmp_path, tool=10)

    def down(url, headers=None):
        """Fail as a network outage does."""
        raise urllib.error.URLError("down")

    with pytest.raises(errors.ReadinessError, match="could not check tool"):
        cli_update.update(tmp_path, "tool", down, now=NOW)
    assert data.read_rows(tmp_path)["tool"]["serial"] == 10


def run(argv, capsys):
    """Run the CLI and return (exit code, stdout, stderr)."""
    code = cli.main(argv)
    out, err = capsys.readouterr()
    return code, out, err


def test_the_printed_line_names_the_version_and_the_skills(tmp_path, capsys, monkeypatch):
    """A candidate's line is the data commit's title."""
    monkeypatch.setattr(shared, "get", fake_pypi(100, {"tool": (55, *skill("tool"))}))
    assert run(["update", str(tmp_path), "tool"], capsys) == (0, "chore: update tool to 1.0, 1 with skills\n", "")


def test_an_unchecked_project_prints_zero_skills(tmp_path, capsys, monkeypatch):
    """No repository to check still fits the line's shape."""
    doc = pypi_doc("tool", repo="https://example.com/x")
    monkeypatch.setattr(shared, "get", fake_pypi(100, {"tool": (55, doc, None)}))
    assert run(["update", str(tmp_path), "tool"], capsys)[1] == "chore: update tool to 1.0, 0 with skills\n"


def test_the_printed_line_says_not_a_candidate(tmp_path, capsys, monkeypatch):
    """A project that fails the filter says so, under the same shape."""
    monkeypatch.setattr(shared, "get", fake_pypi(100, {"tool": (55, pypi_doc("tool", console=False), None)}))
    assert run(["update", str(tmp_path), "tool"], capsys)[1] == "chore: update tool, not a candidate\n"


def test_a_removed_row_exits_1_with_no_usage_line(tmp_path, capsys, monkeypatch):
    """The grammar was fine, so the refusal carries no usage, and stdout stays empty."""
    stored(tmp_path, gone=0)
    monkeypatch.setattr(shared, "get", no_call)
    code, out, err = run(["update", str(tmp_path), "gone"], capsys)
    assert code == cli.EXIT_ERROR
    assert out == ""
    assert err == "yavapy-harvester: gone was removed: its row has serial 0\n"
