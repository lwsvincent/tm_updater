import tomllib
from pathlib import Path

def update_version():
    root_dir = Path(__file__).parent.parent
    pyproject_path = root_dir / "pyproject.toml"
    init_path = root_dir / "src" / "updater" / "__init__.py"

    if not pyproject_path.exists():
        print(f"Error: {pyproject_path} not found")
        return

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
        version = data.get("project", {}).get("version")

    if not version:
        print("Error: version not found in pyproject.toml")
        return

    if not init_path.exists():
        print(f"Error: {init_path} not found")
        return

    with open(init_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    with open(init_path, "w", encoding="utf-8") as f:
        for line in lines:
            if line.startswith("__version__ ="):
                f.write(f'__version__ = "{version}"\n')
            else:
                f.write(line)

    print(f"Updated {init_path} to version {version}")

if __name__ == "__main__":
    update_version()
