"""Tests for reading and writing the data files."""

from yavapy_harvester import data


def row(name, **cells):
    """Return a full row for `name`, empty unless given."""
    return {column: None for column in data.COLUMNS} | {"name": name, "serial": 1} | cells


def test_rows_round_trip_with_empty_cells_as_none(tmp_path):
    """Integers come back as integers, and empty cells as None."""
    rows = {"a": row("a", summary='says "hi", twice', skill_count=0), "b": row("b", skill_count=None)}
    data.write_rows(tmp_path, rows)
    assert data.read_rows(tmp_path) == rows


def test_a_short_row_reads_with_its_missing_cells_as_none(tmp_path):
    """A row typed by hand as a name and a serial reads like a full one."""
    (tmp_path / data.PROJECTS).write_text(",".join(data.COLUMNS) + "\nfoo,0\n")
    assert data.read_rows(tmp_path) == {"foo": row("foo", serial=0)}


def test_rows_are_sorted_by_name(tmp_path):
    """The file lists rows by name, whatever order they came in."""
    data.write_rows(tmp_path, {"zed": row("zed"), "abc": row("abc")})
    lines = (tmp_path / data.PROJECTS).read_text().splitlines()
    assert lines[0] == ",".join(data.COLUMNS)
    assert [line.split(",")[0] for line in lines[1:]] == ["abc", "zed"]


def test_missing_files_read_as_empty_and_first_run(tmp_path):
    """An empty directory has no rows and no marks yet."""
    assert data.read_rows(tmp_path) == {}
    assert data.read_marks(tmp_path) is None


def test_empty_marks_file_reads_as_first_run(tmp_path):
    """An empty or blank marks.json means no marks yet, like a missing one."""
    path = tmp_path / data.MARKS
    for text in ("", "\n"):
        path.write_text(text)
        assert data.read_marks(tmp_path) is None


def test_marks_round_trip_and_leave_no_partial(tmp_path):
    """Marks come back as written, and the write leaves only the real file."""
    data.write_marks(tmp_path, {"catchup": 9})
    assert data.read_marks(tmp_path) == {"catchup": 9}
    assert sorted(path.name for path in tmp_path.iterdir()) == [data.MARKS]


def test_names_round_trip_and_leave_no_partial(tmp_path):
    """Names come back in order, an empty list is an empty file, and only the file remains."""
    path = tmp_path / "list.txt"
    data.write_names(path, ["b", "a"])
    assert data.read_names(path) == ["b", "a"]
    data.write_names(path, [])
    assert path.read_text() == ""
    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["list.txt"]


def test_old_forward_key_reads_as_catchup(tmp_path):
    """A marks.json from before the rename keeps its value."""
    (tmp_path / data.MARKS).write_text('{"forward": 9}\n')
    assert data.read_marks(tmp_path) == {"catchup": 9}
