"""
Contract tests for docs/specs/target_resolution_spec.md.

Every test injects exe_dir / cwd explicitly - no dependence on where the test
runner happens to be started from.
"""

from pathlib import Path

import pytest

from updater.target import (
    ORIGIN_BUILTIN,
    ORIGIN_EXE,
    ORIGIN_PROJECT,
    TargetError,
    find_exe_config,
    find_project_root,
    find_target_python,
    resolve_source,
    resolve_target,
    resolve_venv_arg,
)

VENV_PY = Path("venv") / "Scripts" / "python.exe"


def _make_project(root: Path, venv_name: str = "venv") -> Path:
    """Create <root>/<venv_name>/Scripts/python.exe and return the exe path."""
    python_exe = root / venv_name / "Scripts" / "python.exe"
    python_exe.parent.mkdir(parents=True, exist_ok=True)
    python_exe.write_text("", encoding="utf-8")
    return python_exe


def _write_toml(root: Path, source: str, packages: list[str]) -> Path:
    toml_file = root / "updater.toml"
    pkg_lines = "\n".join(f'    "{p}",' for p in packages)
    # TOML literal string (single quotes) so UNC backslashes need no escaping.
    toml_file.write_text(
        f"[updater]\nsource = '{source}'\npackages = [\n{pkg_lines}\n]\n",
        encoding="utf-8",
    )
    return toml_file


class TestExplicitProject:
    def test_project_venv_wins_over_cwd(self, tmp_path: Path) -> None:
        project = tmp_path / "ProjA"
        expected = _make_project(project)
        # A decoy venv next to the exe and next to the cwd must be ignored.
        _make_project(tmp_path / "tools")
        _make_project(tmp_path / "cwd")

        target = resolve_target(
            str(project),
            exe_dir=tmp_path / "tools",
            cwd=tmp_path / "cwd",
        )

        assert target.project_root == project.resolve()
        assert target.python_exe == expected
        assert target.config_origin == ORIGIN_BUILTIN

    def test_project_without_toml_still_finds_venv(self, tmp_path: Path) -> None:
        project = tmp_path / "ProjB"
        _make_project(project, venv_name=".venv")
        target = resolve_target(
            str(project), exe_dir=tmp_path, cwd=tmp_path
        )
        assert target.python_exe == project / ".venv" / "Scripts" / "python.exe"

    def test_missing_project_raises(self, tmp_path: Path) -> None:
        with pytest.raises(TargetError, match="not found"):
            resolve_target(str(tmp_path / "nope"), tmp_path, tmp_path)

    def test_project_pointing_at_file_raises(self, tmp_path: Path) -> None:
        a_file = tmp_path / " readme.txt"
        a_file.write_text("x", encoding="utf-8")
        with pytest.raises(TargetError, match="not a directory"):
            resolve_target(str(a_file), tmp_path, tmp_path)


class TestProjectTakesPrecedenceOverExeConfig:
    def test_project_toml_overrides_exe_toml(self, tmp_path: Path) -> None:
        project = tmp_path / "ProjC"
        _make_project(project)
        _write_toml(project, r"\\server\proj_c_pkgs", ["test-matrix"])
        exe_dir = tmp_path / "tools"
        exe_dir.mkdir()
        _write_toml(exe_dir, r"\\server\default_pkgs", ["scope_driver"])

        target = resolve_target(str(project), exe_dir=exe_dir, cwd=tmp_path)

        assert target.config_origin == ORIGIN_PROJECT
        assert target.config.source == r"\\server\proj_c_pkgs"
        assert target.config.packages == ["test-matrix"]

    def test_no_project_toml_falls_back_to_exe_toml(self, tmp_path: Path) -> None:
        project = tmp_path / "ProjD"
        _make_project(project)
        exe_dir = tmp_path / "tools"
        exe_dir.mkdir()
        _write_toml(exe_dir, r"\\server\default_pkgs", ["scope_driver"])

        target = resolve_target(str(project), exe_dir=exe_dir, cwd=tmp_path)

        assert target.config_origin == ORIGIN_EXE
        assert target.config.source == r"\\server\default_pkgs"


class TestLegacyLayoutRegression:
    """exe installed inside the project (pre --project) must keep working."""

    def test_exe_inside_project_resolves_project_root(self, tmp_path: Path) -> None:
        project = tmp_path / "TestMatrix"
        _make_project(project)
        exe_dir = project / "updater"
        exe_dir.mkdir()
        _write_toml(exe_dir, r"\\pnt52\packages", ["test-matrix"])

        target = resolve_target(None, exe_dir=exe_dir, cwd=exe_dir)

        assert target.project_root == project.resolve()
        assert target.python_exe == project / VENV_PY
        assert target.config_origin == ORIGIN_EXE

    def test_custom_venv_name_from_config_is_honoured(self, tmp_path: Path) -> None:
        project = tmp_path / "TestMatrix2"
        _make_project(project, venv_name="tm_env")
        exe_dir = project / "updater"
        exe_dir.mkdir()
        (exe_dir / "updater.toml").write_text(
            "[updater]\nsource = '\\\\pnt52\\packages'\nvenv_name = 'tm_env'\n",
            encoding="utf-8",
        )

        target = resolve_target(None, exe_dir=exe_dir, cwd=exe_dir)

        assert target.python_exe == project / "tm_env" / "Scripts" / "python.exe"

    def test_no_marker_anywhere_falls_back_to_exe_dir(self, tmp_path: Path) -> None:
        exe_dir = tmp_path / "tools"
        exe_dir.mkdir()

        target = resolve_target(None, exe_dir=exe_dir, cwd=tmp_path / "elsewhere")

        assert target.project_root == exe_dir.resolve()
        assert target.python_exe is None
        assert target.config_origin == ORIGIN_BUILTIN


class TestProjectRootDiscovery:
    def test_walks_up_from_cwd(self, tmp_path: Path) -> None:
        project = tmp_path / "ProjE"
        _make_project(project)
        deep = project / "src" / "pkg" / "sub"
        deep.mkdir(parents=True)

        assert find_project_root(deep, ["venv", ".venv"]) == project.resolve()

    def test_updater_toml_alone_marks_a_project(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, r"\\server\pkgs", ["test-matrix"])
        assert find_project_root(tmp_path, ["venv"]) == tmp_path.resolve()


class TestVenvArg:
    def test_strict_resolution_returns_python(self, tmp_path: Path) -> None:
        expected = _make_project(tmp_path / "ProjF")
        assert resolve_venv_arg(str(tmp_path / "ProjF" / "venv"), ["venv"]) == expected

    def test_missing_venv_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(TargetError, match="venv directory not found"):
            resolve_venv_arg(str(tmp_path / "ghost" / "venv"), ["venv"])

    def test_venv_dir_without_python_raises(self, tmp_path: Path) -> None:
        (tmp_path / "venv").mkdir()
        with pytest.raises(TargetError, match="Scripts/python.exe"):
            resolve_venv_arg(str(tmp_path / "venv"), ["venv"])


class TestSourceResolution:
    def test_relative_source_anchors_at_config_dir(self, tmp_path: Path) -> None:
        project = tmp_path / "ProjG"
        _make_project(project)
        _write_toml(project, "packages", ["test-matrix"])

        target = resolve_target(str(project), exe_dir=tmp_path, cwd=tmp_path)

        assert resolve_source(target.config) == (project / "packages").resolve()

    def test_unc_source_is_never_rewritten(self, tmp_path: Path) -> None:
        """Python 3.11 reports UNC is_absolute() == False; it must stay intact."""
        project = tmp_path / "ProjUNC"
        _make_project(project)
        _write_toml(project, r"\\pnt52\packages", ["test-matrix"])

        target = resolve_target(str(project), exe_dir=tmp_path, cwd=tmp_path)

        assert resolve_source(target.config) == Path(r"\\pnt52\packages")

    def test_absolute_source_untouched(self, tmp_path: Path) -> None:
        project = tmp_path / "ProjH"
        _make_project(project)
        _write_toml(project, r"C:\pkgs", ["test-matrix"])

        target = resolve_target(str(project), exe_dir=tmp_path, cwd=tmp_path)

        assert resolve_source(target.config) == Path(r"C:\pkgs").resolve()


class TestExeConfigLookup:
    def test_finds_toml_beside_exe(self, tmp_path: Path) -> None:
        exe_dir = tmp_path / "updater"
        exe_dir.mkdir()
        toml = _write_toml(exe_dir, r"\\server\pkgs", ["test-matrix"])

        assert find_exe_config(exe_dir) == toml

    def test_falls_back_to_exe_dir_when_absent(self, tmp_path: Path) -> None:
        exe_dir = tmp_path / "updater"
        exe_dir.mkdir()

        assert find_exe_config(exe_dir) == exe_dir / "updater.toml"


class TestTargetHelpers:
    def test_find_target_python_checks_project_then_parent(
        self, tmp_path: Path
    ) -> None:
        parent_venv = _make_project(tmp_path, venv_name="venv")
        project = tmp_path / "ProjI"
        project.mkdir()

        assert find_target_python(project, ["venv"]) == parent_venv

    def test_describe_reports_missing_venv(self, tmp_path: Path) -> None:
        exe_dir = tmp_path / "tools"
        exe_dir.mkdir()
        target = resolve_target(None, exe_dir=exe_dir, cwd=tmp_path)

        summary = target.describe()
        assert "Venv: not found" in summary
        assert str(exe_dir.resolve()) in summary


class TestGuiTargetApi:
    """Api must expose the target and allow switching it at runtime."""

    def _api(self, tmp_path: Path):
        from updater.gui.app import Api

        project = tmp_path / "ProjLive"
        _make_project(project)
        _write_toml(project, r"\\server\live", ["test-matrix"])
        target = resolve_target(str(project), exe_dir=tmp_path, cwd=tmp_path)
        return Api(target.config, target.python_exe, target), project

    def test_get_target_reports_project_venv_and_source(self, tmp_path: Path) -> None:
        api, project = self._api(tmp_path)

        payload = api.get_target()

        assert payload["project"] == str(project.resolve())
        assert payload["venv"] == str((project / "venv").resolve())
        # pathlib appends a separator to UNC roots; compare as paths.
        assert Path(payload["source"]) == Path(r"\\server\live")
        assert payload["error"] == ""

    def test_switch_target_rebinds_config_and_venv(self, tmp_path: Path) -> None:
        api, _ = self._api(tmp_path)
        other = tmp_path / "ProjOther"
        _make_project(other, venv_name=".venv")
        _write_toml(other, "packages", ["scope_driver"])

        result = api.set_target(str(other))

        assert result["error"] is None
        assert api._config.packages == ["scope_driver"]
        assert api._python_exe == other / ".venv" / "Scripts" / "python.exe"
        # relative source now anchors at the new project
        assert api._source_path() == (other / "packages").resolve()

    def test_bad_path_keeps_previous_target(self, tmp_path: Path) -> None:
        api, project = self._api(tmp_path)

        result = api.set_target(str(tmp_path / "does-not-exist"))

        assert "not found" in str(result["error"])
        assert api.get_target()["project"] == str(project.resolve())
