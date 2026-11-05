"""The two failure classes the CLI reports."""


class ReadinessError(Exception):
    """Something the run needed was missing, found before the first write."""


class RuntimeFailure(Exception):
    """The run stopped partway, after something was written."""
