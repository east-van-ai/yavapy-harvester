"""The files: one row per candidate in the CSV, the mark in marks.json, and the backfill list."""

import csv
import json
import os
from pathlib import Path

COLUMNS = (
    "name",
    "serial",
    "version",
    "summary",
    "classifiers",
    "released_at",
    "checked_at",
    "repo_url",
    "tag",
    "skill_count",
    "skill_path",
    "topics",
    "license",
    "keywords",
)
INTEGERS = {"serial", "skill_count"}
PROJECTS = "projects.csv"
MARKS = "marks.json"


def parse(row):
    """Return a CSV row as a dict, with empty or missing cells as None and counts as integers."""
    return {
        key: None if value in ("", None) else int(value) if key in INTEGERS else value for key, value in row.items()
    }


def read_rows(directory):
    """Return the rows of the CSV keyed by name, or {} when it is missing."""
    path = Path(directory) / PROJECTS
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as file:
        return {row["name"]: parse(row) for row in csv.DictReader(file)}


def write_rows(directory, rows):
    """Write `rows`, a {name: row} map, to the CSV, sorted by name."""
    path = Path(directory) / PROJECTS
    partial = path.with_suffix(".csv.partial")
    with partial.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, COLUMNS, lineterminator="\n")
        writer.writeheader()
        for name in sorted(rows):
            writer.writerow({key: "" if value is None else value for key, value in rows[name].items()})
    os.replace(partial, path)


def read_marks(directory):
    """Return the marks, or None before the first run.

    A missing file and an empty one both mean the first run. An old `forward`
    key reads as `catchup`, and the next write saves the new key.
    """
    path = Path(directory) / MARKS
    text = path.read_text().strip() if path.exists() else ""
    marks = json.loads(text) if text else None
    if marks and "forward" in marks:
        marks["catchup"] = marks.pop("forward")
    return marks


def write_marks(directory, marks):
    """Write the marks to marks.json."""
    path = Path(directory) / MARKS
    partial = path.with_suffix(".json.partial")
    partial.write_text(json.dumps(marks, indent=2, sort_keys=True) + "\n")
    os.replace(partial, path)


def read_names(path):
    """Return the backfill list at `path`, one name per line."""
    return Path(path).read_text(encoding="utf-8").splitlines()


def write_names(path, names):
    """Write the backfill list to `path`, replacing the file in one step."""
    path = Path(path)
    partial = path.with_name(f"{path.name}.partial")
    partial.write_text("".join(f"{name}\n" for name in names), encoding="utf-8")
    os.replace(partial, path)
