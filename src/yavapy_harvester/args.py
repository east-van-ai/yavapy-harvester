"""The yavapy-harvester command line's vocabulary: the parser and its helpers."""

import argparse
import sys
from importlib import metadata

from yavapy_harvester import cli_backfill, cli_catchup, cli_update, cli_walkdown, shared

PROG = "yavapy-harvester"
MONOCHROME = {"color": False} if sys.version_info >= (3, 14) else {}
PATHS = """\
paths:
  DIR       the data directory holding the CSV and marks.json.
  FILE      the backfill list, one project name per line.
  NAME      the one project to check.
  Paths come right after COMMAND, then options in any order."""


def leading_paths(tokens):
    """Return the tokens ahead of the first flag."""
    paths = []
    for token in tokens:
        if token.startswith("-"):
            break
        paths.append(token)
    return paths


def count(text):
    """Return `text` as an integer of at least 0, for argparse's `type=`."""
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be at least 0: {text!r}")
    return value


def add_limit(command):
    """Add the --limit flag to a command's subparser."""
    command.add_argument(
        "--limit",
        type=count,
        default=shared.DEFAULT_LIMIT,
        metavar="N",
        help=f"check at most N projects (default: {shared.DEFAULT_LIMIT})",
    )


def add_walkdown(subparsers):
    """Add the `walkdown` subparser and return it."""
    walkdown = subparsers.add_parser(
        "walkdown", help=cli_walkdown.HELP, usage=cli_walkdown.USAGE, allow_abbrev=False
    )
    walkdown.add_argument_group("paths").add_argument("dir", metavar="DIR", nargs="?")
    add_limit(walkdown)
    return walkdown


def add_catchup(subparsers):
    """Add the `catchup` subparser and return it."""
    catchup = subparsers.add_parser(
        "catchup", help=cli_catchup.HELP, usage=cli_catchup.USAGE, allow_abbrev=False
    )
    catchup.add_argument_group("paths").add_argument("dir", metavar="DIR", nargs="?")
    add_limit(catchup)
    return catchup


def add_backfill(subparsers):
    """Add the `backfill` subparser and return it."""
    backfill = subparsers.add_parser(
        "backfill", help=cli_backfill.HELP, usage=cli_backfill.USAGE, allow_abbrev=False
    )
    paths = backfill.add_argument_group("paths")
    paths.add_argument("dir", metavar="DIR", nargs="?")
    paths.add_argument("file", metavar="FILE", nargs="?")
    add_limit(backfill)
    return backfill


def add_update(subparsers):
    """Add the `update` subparser and return it."""
    update = subparsers.add_parser("update", help=cli_update.HELP, usage=cli_update.USAGE, allow_abbrev=False)
    paths = update.add_argument_group("paths")
    paths.add_argument("dir", metavar="DIR", nargs="?")
    paths.add_argument("name", metavar="NAME", nargs="?")
    return update


def build_parser():
    """Return the top-level parser with every command's subparser."""
    usage = "\n       ".join([cli_walkdown.USAGE, cli_catchup.USAGE, cli_backfill.USAGE, cli_update.USAGE, f"{PROG} version"])
    parser = argparse.ArgumentParser(
        prog=PROG,
        usage=usage,
        epilog=PATHS,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
        **MONOCHROME,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=version_line(),
        help="print the installed version and exit",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)
    add_walkdown(subparsers)
    add_catchup(subparsers)
    add_backfill(subparsers)
    add_update(subparsers)
    subparsers.add_parser("version", help="print the installed version and exit", allow_abbrev=False)
    return parser


def command_help(add_command):
    """Return one command's own `--help` text, as argparse prints it."""
    subparsers = argparse.ArgumentParser(prog=PROG, **MONOCHROME).add_subparsers()
    return add_command(subparsers).format_help()


def installed_version():
    """Return the version of the installed yavapy-harvester distribution."""
    try:
        return metadata.version("yavapy-harvester")
    except metadata.PackageNotFoundError:
        return "unknown (not installed)"


def version_line():
    """Return the program name and the installed version on one line."""
    return f"{PROG} {installed_version()}"
