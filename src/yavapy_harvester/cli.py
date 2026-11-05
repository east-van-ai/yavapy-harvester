"""
# ==============================================
# East Van AI -- AI for the rest of us!
# https://github.com/east-van-ai/yavapy-harvester
# contact: east-van-ai@proton.me
# license: MIT
# ==============================================

        YavaPy harvester

Yet Another Virtual Aggregator for PyPI. Builds a CSV directory of the
Agent Skills that live beside published Python command-line tools. Reach for
`walkdown` for the newest, `catchup` to climb from its mark, `backfill` to work
through the past, and `update` to check one project again.

Run a command with nothing after it for its own page.

piped input:
    yavapy-harvester reads none.

exit codes:
    0:     success, and documentation
    1:     yavapy-harvester's own error: a bad command line, a missing directory or
           list, or a run that could not reach PyPI or GitHub
    2:     an unknown command, an unknown option, or a bad value
"""

import sys
from collections import namedtuple

from yavapy_harvester import (
    args,
    cli_backfill,
    cli_catchup,
    cli_update,
    cli_walkdown,
    errors,
)

# 2 is argparse's own exit; it never returns through main.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_ARGPARSE = 2

Command = namedtuple("Command", "bare usage slots action")
"""A command word's answer to being typed alone, its usage line, the path slots it
reads, and the action a full invocation runs.

`bare` returns the text for the bare word; `action` runs the command. For `version`,
both read from `version_line`, since running the command answers the bare word.
"""


def command_page(module, add_command):
    """Return a command's answer to its bare word: its docstring, then its --help."""
    doc = module.__doc__.strip("\n")  # not strip(): the title's indent is layout
    return f"{doc}\n\n{args.command_help(add_command).rstrip()}"


COMMANDS = {
    "walkdown": Command(
        lambda: command_page(cli_walkdown, args.add_walkdown),
        cli_walkdown.USAGE,
        cli_walkdown.SLOTS,
        lambda paths, parsed: cli_walkdown.run(*paths, parsed),
    ),
    "catchup": Command(
        lambda: command_page(cli_catchup, args.add_catchup),
        cli_catchup.USAGE,
        cli_catchup.SLOTS,
        lambda paths, parsed: cli_catchup.run(*paths, parsed),
    ),
    "backfill": Command(
        lambda: command_page(cli_backfill, args.add_backfill),
        cli_backfill.USAGE,
        cli_backfill.SLOTS,
        lambda paths, parsed: cli_backfill.run(*paths, parsed),
    ),
    "update": Command(
        lambda: command_page(cli_update, args.add_update),
        cli_update.USAGE,
        cli_update.SLOTS,
        lambda paths, parsed: cli_update.run(*paths, parsed),
    ),
    "version": Command(
        args.version_line,
        "yavapy-harvester version",
        (),
        lambda paths, parsed: print(args.version_line()),
    ),
}


def usage_error(usage, message):
    """Report a command line the tool could not read, with the matching usage."""
    sys.stdout.flush()
    print(f"yavapy-harvester: {message}", file=sys.stderr)
    print(f"Usage: {usage}", file=sys.stderr)
    return EXIT_ERROR


def readiness_error(message):
    """Report what the run needed and did not find, with no usage line."""
    sys.stdout.flush()
    print(f"yavapy-harvester: {message}", file=sys.stderr)
    return EXIT_ERROR


def runtime_error(message):
    """Report a run that stopped partway, naming what was written."""
    sys.stdout.flush()
    print(f"yavapy-harvester: {message}", file=sys.stderr)
    return EXIT_ERROR


def main(argv=None):
    """Parse arguments, run the matching command, return an exit code."""
    tokens = list(sys.argv[1:] if argv is None else argv)

    if not tokens:
        print(f"{__doc__.strip()}\n\n{args.build_parser().format_help().rstrip()}")
        return EXIT_OK

    # A command word and nothing else is a question, and its own page answers.
    if len(tokens) == 1 and tokens[0] in COMMANDS:
        print(COMMANDS[tokens[0]].bare())
        return EXIT_OK

    parser = args.build_parser()
    parsed, extras = parser.parse_known_args(tokens)

    if any(extra.startswith("-") for extra in extras):
        parser.parse_args(tokens)  # argparse names the flag better, exit 2

    paths = args.leading_paths(tokens[1:])

    command = COMMANDS[parsed.command]

    if len(paths) < len(command.slots):
        needed = " and ".join(command.slots)
        if len(command.slots) > 1:
            needed = f"both {needed}"
        return usage_error(command.usage, f"{parsed.command} needs {needed}")

    # A word past the slots is a stray, and so is one argparse left over after a flag.
    strays = paths[len(command.slots) :] or extras
    if strays:
        last = command.slots[-1] if command.slots else "it"
        return usage_error(
            command.usage,
            f"{parsed.command} takes nothing after {last}: {strays[0]!r}",
        )

    try:
        command.action(paths, parsed)
    except errors.ReadinessError as failure:
        return readiness_error(str(failure))
    except errors.RuntimeFailure as failure:
        return runtime_error(str(failure))

    return EXIT_OK
