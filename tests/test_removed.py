"""Tests for rows with serial 0, which the bulk commands leave alone."""

from test_harvest import NOW, fake_pypi, skill

from yavapy_harvester import cli_backfill, cli_catchup, cli_walkdown, data

HEADER = ",".join(data.COLUMNS)


def removed(directory, *names):
    """Write a CSV holding `names` as short, hand-typed rows with serial 0."""
    lines = [HEADER, *(f"{name},0" for name in names)]
    (directory / data.PROJECTS).write_text("\n".join(lines) + "\n")


def counting(get):
    """Return `get` wrapped to record the project lookups it serves, and the list they land in."""
    calls = []

    def wrapped(url, headers=None):
        """Record a project lookup, then serve the fixture body."""
        if url.startswith("https://pypi.org/pypi/"):
            calls.append(url)
        return get(url, headers)

    return wrapped, calls


def lookup(name):
    """Return the URL of the project lookup for `name`."""
    return f"https://pypi.org/pypi/{name}/json"


def test_walkdown_passes_a_removed_row_and_keeps_going(tmp_path):
    """A removed row gets no call and does not stop the run, and the name below it is checked."""
    removed(tmp_path, "gone")
    get, calls = counting(fake_pypi(120, {"gone": (120, *skill("gone")), "below": (110, *skill("below"))}))
    assert cli_walkdown.walkdown(tmp_path, get, now=NOW) == (1, 1, 1, 110)
    assert calls == [lookup("below")]
    stored = data.read_rows(tmp_path)
    assert stored["gone"]["serial"] == 0
    assert stored["gone"]["version"] is None
    assert stored["below"]["serial"] == 110


def test_walkdown_does_not_count_a_removed_row_toward_its_limit(tmp_path):
    """With a limit of 1, the one lookup goes to the name under the removed row."""
    removed(tmp_path, "gone")
    get, calls = counting(fake_pypi(120, {"gone": (120, *skill("gone")), "below": (110, *skill("below"))}))
    assert cli_walkdown.walkdown(tmp_path, get, limit=1, now=NOW) == (1, 1, 1, 110)
    assert calls == [lookup("below")]


def test_walkdown_matches_a_removed_row_by_its_normalized_name(tmp_path):
    """An index name spelled another way still finds its removed row."""
    removed(tmp_path, "gone-away")
    get, calls = counting(fake_pypi(120, {"Gone_Away": (120, *skill("Gone_Away"))}))
    assert cli_walkdown.walkdown(tmp_path, get, now=NOW)[0] == 0
    assert calls == []


def test_catchup_jumps_a_removed_row_and_moves_its_mark(tmp_path):
    """A removed row gets no call and no count, and the mark goes past it."""
    removed(tmp_path, "gone")
    data.write_marks(tmp_path, {"catchup": 100})
    get, calls = counting(fake_pypi(120, {"gone": (110, *skill("gone")), "above": (115, *skill("above"))}))
    assert cli_catchup.catchup(tmp_path, get, limit=1, now=NOW) == (1, 1, 1, 120)
    assert calls == [lookup("above")]
    assert data.read_marks(tmp_path) == {"catchup": 120}
    assert data.read_rows(tmp_path)["gone"]["serial"] == 0


def test_backfill_takes_a_removed_name_off_with_no_call(tmp_path):
    """The name comes off the list like any other with a row, and the row stays."""
    removed(tmp_path, "gone")
    names = tmp_path / "backfill.txt"
    names.write_text("gone\n")
    get, calls = counting(fake_pypi(120, {"gone": (110, *skill("gone"))}))
    assert cli_backfill.backfill(tmp_path, names, get, now=NOW) == (0, 0, 0, 0)
    assert calls == []
    assert names.read_text() == ""
    assert data.read_rows(tmp_path)["gone"]["serial"] == 0


def test_a_short_row_comes_back_full_width_after_a_write(tmp_path):
    """Writing another row puts the commas back on a hand-typed one."""
    removed(tmp_path, "gone")
    get = fake_pypi(120, {"below": (110, *skill("below"))})
    cli_walkdown.walkdown(tmp_path, get, now=NOW)
    lines = (tmp_path / data.PROJECTS).read_text().splitlines()
    assert "gone,0" + "," * (len(data.COLUMNS) - 2) in lines
