"""Print the package version for build scripts (single line, no other output)."""

import pathlib
import sys

import tomllib


def main() -> int:
    pyproject = pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml"
    with open(pyproject, "rb") as f:
        print(tomllib.load(f)["project"]["version"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
