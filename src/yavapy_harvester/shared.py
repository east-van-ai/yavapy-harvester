"""Helpers shared across commands."""

import gzip
import urllib.error
import urllib.request
from pathlib import Path

from yavapy_harvester.errors import ReadinessError

USER_AGENT = "yavapy-harvester (+https://github.com/east-van-ai/yavapy-harvester)"
TIMEOUT = 60
DEFAULT_LIMIT = 200


def get(url, headers=None):
    """Return the body of a GET request to `url`, or None when it answers 404.

    The request asks for gzip, and a gzipped answer comes back unpacked. Every
    other HTTP or network failure raises, so the caller decides whether the run
    goes on.
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip", **(headers or {})}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read()
            return gzip.decompress(body) if response.headers.get("Content-Encoding") == "gzip" else body
    except urllib.error.HTTPError as failure:
        if failure.code == 404:
            return None
        raise


def require_directory(path):
    """Refuse a data directory that does not exist."""
    if not Path(path).is_dir():
        raise ReadinessError(f"no directory at {path}")
