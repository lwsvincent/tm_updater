"""Updater microservice - manages package updates for Test Matrix."""

import sys

__version__ = "1.2.0"


def get_version() -> str:
    """
    Return the version string.
    In development (running from source), returns 'develop version'.
    In production (frozen EXE), returns the hardcoded __version__.
    """
    if getattr(sys, "frozen", False):
        return __version__
    return "develop version"
