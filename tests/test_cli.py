"""Tests for the yavapy-harvester command surface."""

import pytest

from yavapy_harvester import (
    args,
    cli,
    cli_backfill,
    cli_catchup,
    cli_update,
    cli_walkdown,
    shared,
)


def run(argv, capsys):
    """Run the CLI and return (exit code, stdout, stderr), whether it returned or exited."""
    try:
        code = cli.main(argv)
    except SystemExit as exit_:
        code = exit_.code
    out, err = capsys.readouterr()
    return code, out, err


def test_bare_tool_prints_the_banner_and_help(capsys):
    """Bare `yavapy-harvester` prints the module docstring, then --help."""
    code, out, _ = run([], capsys)
    assert code == cli.EXIT_OK
    assert "        YavaPy harvester\n" in out
    assert "usage: yavapy-harvester walkdown DIR" in out
    assert "yavapy-harvester catchup DIR" in out
    assert "yavapy-harvester backfill DIR FILE" in out
    assert "yavapy-harvester update DIR NAME" in out


@pytest.mark.parametrize(
    ("word", "module", "add"),
    [
        ("walkdown", cli_walkdown, args.add_walkdown),
        ("catchup", cli_catchup, args.add_catchup),
        ("backfill", cli_backfill, args.add_backfill),
        ("update", cli_update, args.add_update),
    ],
)
def test_bare_command_prints_its_page(word, module, add, capsys):
    """A command word alone prints its docstring, ending in its own --help."""
    code, out, _ = run([word], capsys)
    assert code == cli.EXIT_OK
    assert out.startswith(module.__doc__.strip("\n"))
    assert out.rstrip().endswith(args.command_help(add).rstrip())


@pytest.mark.parametrize(
    ("word", "module"),
    [("walkdown", cli_walkdown), ("catchup", cli_catchup), ("backfill", cli_backfill), ("update", cli_update)],
)
def test_command_help_starts_with_its_usage(word, module, capsys):
    """`--help` on a command opens on its own usage line."""
    code, out, _ = run([word, "--help"], capsys)
    assert code == cli.EXIT_OK
    assert out.startswith(f"usage: {module.USAGE}")


def test_version_both_spellings(capsys):
    """`version` and `--version` print the same line."""
    assert run(["version"], capsys)[1] == run(["--version"], capsys)[1] == f"{args.version_line()}\n"


@pytest.mark.parametrize(("word", "module"), [("walkdown", cli_walkdown), ("catchup", cli_catchup)])
def test_a_flag_and_no_dir_is_a_usage_error(word, module, capsys):
    """A flag with no DIR names the slot and prints the usage."""
    code, _, err = run([word, "--limit", "5"], capsys)
    assert code == cli.EXIT_ERROR
    assert err == f"yavapy-harvester: {word} needs DIR\nUsage: {module.USAGE}\n"


def test_backfill_with_dir_alone_is_a_usage_error(tmp_path, capsys):
    """`backfill` names both of its slots."""
    code, _, err = run(["backfill", str(tmp_path)], capsys)
    assert code == cli.EXIT_ERROR
    assert err == f"yavapy-harvester: backfill needs both DIR and FILE\nUsage: {cli_backfill.USAGE}\n"


def test_update_with_dir_alone_is_a_usage_error(tmp_path, capsys):
    """`update` names both of its slots."""
    code, _, err = run(["update", str(tmp_path)], capsys)
    assert code == cli.EXIT_ERROR
    assert err == f"yavapy-harvester: update needs both DIR and NAME\nUsage: {cli_update.USAGE}\n"


def test_update_stray_past_name_is_refused(capsys, monkeypatch):
    """A word past NAME is a stray."""
    monkeypatch.setattr(cli_update, "run", lambda *a: pytest.fail("run started"))
    code, _, err = run(["update", "D", "N", "stray"], capsys)
    assert code == cli.EXIT_ERROR
    assert err == f"yavapy-harvester: update takes nothing after NAME: 'stray'\nUsage: {cli_update.USAGE}\n"


def test_update_takes_no_limit(tmp_path, capsys):
    """One name is its own cap, so --limit is an unknown option."""
    assert run(["update", str(tmp_path), "N", "--limit", "5"], capsys)[0] == cli.EXIT_ARGPARSE


def test_file_after_a_flag_is_not_read_as_file(tmp_path, capsys, monkeypatch):
    """FILE must come ahead of the flags, however argparse would back-fill it."""
    monkeypatch.setattr(cli_backfill, "run", lambda *a: pytest.fail("run started"))
    code, _, err = run(["backfill", str(tmp_path), "--limit", "5", "list.txt"], capsys)
    assert code == cli.EXIT_ERROR
    assert err.startswith("yavapy-harvester: backfill needs both DIR and FILE")


@pytest.mark.parametrize(
    ("words", "module", "last"),
    [
        (["walkdown", "D"], cli_walkdown, "DIR"),
        (["catchup", "D"], cli_catchup, "DIR"),
        (["backfill", "D", "F"], cli_backfill, "FILE"),
    ],
)
def test_stray_past_the_slots_and_after_the_limit_is_refused(words, module, last, capsys, monkeypatch):
    """A bare word past the last slot, or behind --limit's value, is a stray."""
    monkeypatch.setattr(module, "run", lambda *a: pytest.fail("run started"))
    for tail in (["stray"], ["--limit", "5", "stray"]):
        code, _, err = run([*words, *tail], capsys)
        assert code == cli.EXIT_ERROR
        assert err == f"yavapy-harvester: {words[0]} takes nothing after {last}: 'stray'\nUsage: {module.USAGE}\n"


def test_stray_after_version(capsys):
    """`version` takes no words."""
    code, _, err = run(["version", "x"], capsys)
    assert code == cli.EXIT_ERROR
    assert err.startswith("yavapy-harvester: version takes nothing after it: 'x'")


def test_negative_limit_is_argparse_error(tmp_path, capsys):
    """--limit -1 is a bad value, exit 2."""
    code, _, _ = run(["catchup", str(tmp_path), "--limit", "-1"], capsys)
    assert code == cli.EXIT_ARGPARSE


def test_catchup_without_a_directory(tmp_path, capsys):
    """Running into a missing directory is a readiness error, no usage line."""
    path = tmp_path / "nowhere"
    code, _, err = run(["catchup", str(path)], capsys)
    assert code == cli.EXIT_ERROR
    assert err == f"yavapy-harvester: no directory at {path}\n"


def test_no_colour(monkeypatch, capsys):
    """Help prints no escape codes, even when colour is forced."""
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert "\x1b[" not in run([], capsys)[1]
    assert "\x1b[" not in run(["walkdown"], capsys)[1]
    assert "\x1b[" not in run(["catchup"], capsys)[1]
    assert "\x1b[" not in run(["backfill"], capsys)[1]
    assert "\x1b[" not in run(["update"], capsys)[1]


@pytest.mark.parametrize("word", ["harvest", "run", "forward", "backward"])
def test_old_command_words_are_unknown(word, capsys):
    """Earlier command words are gone, so argparse refuses them."""
    code, _, _ = run([word, "somewhere"], capsys)
    assert code == cli.EXIT_ARGPARSE


def test_backfill_file_in_a_missing_directory(tmp_path, capsys):
    """A FILE with nowhere to live is a readiness error, no usage line."""
    file = tmp_path / "nowhere" / "list.txt"
    code, _, err = run(["backfill", str(tmp_path), str(file)], capsys)
    assert code == cli.EXIT_ERROR
    assert err == f"yavapy-harvester: no list at {file}\n"


def test_backfill_missing_file_stops_with_no_call(tmp_path, capsys, monkeypatch):
    """A mistyped FILE is a readiness error: no index read, and no new list."""
    monkeypatch.setattr(shared, "get", lambda url, headers=None: pytest.fail("called PyPI"))
    file = tmp_path / "typo.txt"
    code, out, err = run(["backfill", str(tmp_path), str(file)], capsys)
    assert code == cli.EXIT_ERROR
    assert (out, err) == ("", f"yavapy-harvester: no list at {file}\n")
    assert not file.exists()


def test_backfill_summary_ends_on_the_names_left(tmp_path, capsys):
    """An empty list makes no call, and the last line reports it."""
    file = tmp_path / "list.txt"
    file.write_text("")
    code, out, _ = run(["backfill", str(tmp_path), str(file)], capsys)
    assert code == cli.EXIT_OK
    assert out == "chore: backfill 0 projects, 0 candidates, 0 with skills, 0 names left\n"


def test_catchup_summary_ends_on_the_mark(tmp_path, capsys, monkeypatch):
    """A first catchup run checks nothing, and the last line reports the mark."""
    index = b'{"meta": {"_last-serial": 100}, "projects": []}'
    monkeypatch.setattr(shared, "get", lambda url, headers=None: index)
    code, out, _ = run(["catchup", str(tmp_path)], capsys)
    assert code == cli.EXIT_OK
    assert out == "chore: catchup 0 projects, 0 candidates, 0 with skills, mark 100\n"


def test_walkdown_summary_ends_on_how_far_it_got(tmp_path, capsys, monkeypatch):
    """An empty index checks nothing, and the last line reports the current serial."""
    index = b'{"meta": {"_last-serial": 100}, "projects": []}'
    monkeypatch.setattr(shared, "get", lambda url, headers=None: index)
    code, out, _ = run(["walkdown", str(tmp_path)], capsys)
    assert code == cli.EXIT_OK
    assert out == "chore: walkdown 0 projects, 0 candidates, 0 with skills, down to 100\n"


def test_longest_realistic_title_is_under_100_characters(tmp_path, capsys):
    """A full list and large counts still fit the house limit on a commit title."""
    file = tmp_path / "list.txt"
    file.write_text("")
    _, out, _ = run(["backfill", str(tmp_path), str(file)], capsys)
    longest = out.strip().replace("0 projects", "9999 projects").replace("0 candidates", "9999 candidates")
    longest = longest.replace("0 with skills", "9999 with skills").replace("0 names left", "9999999 names left")
    assert len(longest) < 100
