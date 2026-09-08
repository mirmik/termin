import importlib.metadata
from pathlib import Path

import pytest

from termin_build import (
    sdk,
    sdk_bundled_python,
    sdk_build_support,
    sdk_package_install,
    sdk_python_install,
    sdk_python_layout,
    sdk_runtime_metadata,
    sdk_wheel_pipeline,
)
from termin_build.package_manifest import PackageEntry


REPO_ROOT = Path(__file__).resolve().parents[3]
FULL_SDK_PROFILE = sdk.load_sdk_profiles(REPO_ROOT).profile("full")


def test_install_target_uses_single_pip_invocation(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    target_dir = tmp_path / "target"
    (sdk_prefix / "lib").mkdir(parents=True)
    for package_path in ("pkg-a", "pkg-b"):
        (repo_root / package_path).mkdir(parents=True)

    packages = [
        PackageEntry("pkg-a", "pkg-a", (), ()),
        PackageEntry("pkg-b", "pkg-b", (), ()),
    ]
    commands = []

    monkeypatch.setattr(sdk_package_install, "_sdk_packages", lambda _repo_root: packages)
    monkeypatch.setattr(sdk_build_support, "_sdk_packages", lambda _repo_root: packages)
    monkeypatch.setattr(sdk_package_install, "_python_bin", lambda: "python")
    monkeypatch.setattr(
        sdk_package_install,
        "_run",
        lambda command, **_kwargs: commands.append(command) or 0,
    )
    stale_pkg_a = target_dir / "pkg_a-0.1.0+old.dist-info"
    stale_pkg_a.mkdir(parents=True)
    (stale_pkg_a / "METADATA").write_text("Name: pkg-a\n", encoding="utf-8")
    stale_pkg_a_module = target_dir / "pkg_a" / "removed_module.py"
    stale_pkg_a_module.parent.mkdir()
    stale_pkg_a_module.write_text("STALE = True\n", encoding="utf-8")
    (stale_pkg_a / "RECORD").write_text(
        "pkg_a/removed_module.py,,\npkg_a-0.1.0+old.dist-info/METADATA,,\n",
        encoding="utf-8",
    )
    stale_pkg_b = target_dir / "pkg_b.egg-info"
    stale_pkg_b.mkdir()
    (stale_pkg_b / "PKG-INFO").write_text("Name: pkg-b\n", encoding="utf-8")
    unrelated = target_dir / "unrelated-1.0.0.dist-info"
    unrelated.mkdir()
    (unrelated / "METADATA").write_text("Name: unrelated\n", encoding="utf-8")

    result = sdk_package_install.install_pip_packages(
        repo_root=repo_root,
        sdk_prefix=sdk_prefix,
        build_dir=repo_root / "build" / "Release",
        target_dir=target_dir,
        editable=False,
        force=True,
    )

    assert result == 0
    assert len(commands) == 1
    command = commands[0]
    assert command[:6] == [
        "python",
        "-m",
        "pip",
        "install",
        "--no-build-isolation",
        "--no-deps",
    ]
    assert "--target" in command
    assert command.count("--no-deps") == 1
    assert str(repo_root / "pkg-a") in command
    assert str(repo_root / "pkg-b") in command
    assert not stale_pkg_a.exists()
    assert not stale_pkg_a_module.exists()
    assert not stale_pkg_b.exists()
    assert unrelated.is_dir()


def test_target_metadata_cleanup_does_not_follow_record_paths_outside_target(
    tmp_path,
):
    target_dir = tmp_path / "site-packages"
    metadata = target_dir / "pkg_a-0.1.0.dist-info"
    metadata.mkdir(parents=True)
    (metadata / "METADATA").write_text("Name: pkg-a\n", encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("KEEP = True\n", encoding="utf-8")
    (metadata / "RECORD").write_text(
        "../../outside.py,,\n",
        encoding="utf-8",
    )

    sdk_runtime_metadata._clear_target_distribution_metadata(target_dir, {"pkg-a"})

    assert outside.is_file()
    assert not metadata.exists()


def test_force_package_cache_cleanup_removes_plain_build_lib_and_nested_egg_info(
    tmp_path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    package_root = repo_root / "example"
    stale_build_lib = package_root / "build" / "lib" / "example"
    stale_build_lib.mkdir(parents=True)
    (stale_build_lib / "removed.py").write_text("STALE = True\n", encoding="utf-8")
    nested_egg_info = package_root / "python" / "example.egg-info"
    nested_egg_info.mkdir(parents=True)
    (nested_egg_info / "SOURCES.txt").write_text("removed.py\n", encoding="utf-8")
    monkeypatch.setattr(
        sdk_build_support,
        "_sdk_packages",
        lambda _repo_root: [PackageEntry("example", "example", (), ())],
    )

    sdk_build_support._clear_python_package_build_caches(repo_root)

    assert not (package_root / "build" / "lib").exists()
    assert not nested_egg_info.exists()


def test_external_runtime_wheels_are_built_from_exact_lock(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    lock_path = repo_root / sdk_runtime_metadata.RUNTIME_LOCK_RELATIVE
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("numpy==2.2.6\nwatchdog==6.0.0\n", encoding="utf-8")
    wheel_dir = repo_root / "build" / "python-runtime" / "external-wheels"
    commands = []

    monkeypatch.setattr(sdk_wheel_pipeline, "_active_sdk_profile", lambda _root: FULL_SDK_PROFILE)
    monkeypatch.setattr(
        sdk_wheel_pipeline,
        "_python_version_and_paths",
        lambda _python: {
            "version": "3.14",
            "soabi": "cpython-314t-x86_64-linux-gnu",
            "free_threaded": True,
            "py_gil_disabled": True,
        },
    )
    monkeypatch.setattr(sdk_wheel_pipeline, "supported_wheel_tags", lambda _python: {"py3-none-any"})
    monkeypatch.setattr(
        sdk_wheel_pipeline,
        "validate_locked_wheelhouse",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        sdk_wheel_pipeline,
        "_run",
        lambda command, **_kwargs: commands.append(command) or 0,
    )

    result = sdk_wheel_pipeline._prepare_external_runtime_wheels(repo_root, wheel_dir, Path("python"))

    assert result == 0
    assert len(commands) == 1
    assert commands[0][:6] == [
        "python",
        "-m",
        "pip",
        "wheel",
        "--no-build-isolation",
        "--no-deps",
    ]
    assert commands[0][6] == "--wheel-dir"
    assert Path(commands[0][7]).parent.parent == wheel_dir.parent
    assert commands[0][8:] == ["-r", str(lock_path)]


def test_sdk_python_build_environment_uses_pinned_tools(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    requirements = repo_root / sdk_build_support.SDK_BUILD_REQUIREMENTS_RELATIVE
    requirements.parent.mkdir(parents=True)
    requirements.write_text("pip==26.1.2\nsetuptools==83.0.0\n", encoding="utf-8")
    environment_root = repo_root / "build" / "python-runtime" / "build-env"
    build_python = environment_root / "bin" / "python"
    build_python.parent.mkdir(parents=True)
    build_python.touch()
    commands = []
    monkeypatch.setattr(sdk_build_support, "_is_windows", lambda: False)
    monkeypatch.setattr(
        sdk_build_support,
        "_python_version_and_paths",
        lambda _python: {
            "version": "3.14",
            "soabi": "cpython-314t-x86_64-linux-gnu",
            "free_threaded": True,
            "py_gil_disabled": True,
        },
    )
    monkeypatch.setattr(
        sdk_build_support,
        "_run",
        lambda command, **_kwargs: commands.append(command) or 0,
    )
    monkeypatch.setattr(sdk_build_support, "_python_pip_error", lambda _python: None)

    result = sdk_build_support._ensure_sdk_python_build_environment(repo_root)

    assert result == build_python
    assert commands == [
        [
            str(build_python),
            "-I",
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--no-deps",
            "-r",
            str(requirements),
        ]
    ]
    assert (environment_root / "python-sdk-build-requirements.txt").read_bytes() == (requirements.read_bytes())


def test_sdk_python_build_environment_repairs_missing_pip(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    requirements = repo_root / sdk_build_support.SDK_BUILD_REQUIREMENTS_RELATIVE
    requirements.parent.mkdir(parents=True)
    requirements.write_text("pip==26.1.2\n", encoding="utf-8")
    environment_root = repo_root / "build" / "python-runtime" / "build-env"
    build_python = environment_root / "bin" / "python"
    build_python.parent.mkdir(parents=True)
    build_python.touch()
    commands = []
    pip_errors = iter(["No module named pip", None])
    monkeypatch.setattr(sdk_build_support, "_is_windows", lambda: False)
    monkeypatch.setattr(
        sdk_build_support,
        "_python_version_and_paths",
        lambda _python: {
            "version": "3.14",
            "soabi": "cpython-314t-x86_64-linux-gnu",
            "free_threaded": True,
            "py_gil_disabled": True,
        },
    )
    monkeypatch.setattr(
        sdk_build_support,
        "_run",
        lambda command, **_kwargs: commands.append(command) or 0,
    )
    monkeypatch.setattr(
        sdk_build_support,
        "_python_pip_error",
        lambda _python: next(pip_errors),
    )

    result = sdk_build_support._ensure_sdk_python_build_environment(repo_root)

    assert result == build_python
    assert commands == [
        [
            str(build_python),
            "-I",
            "-m",
            "ensurepip",
            "--upgrade",
            "--default-pip",
        ],
        [
            str(build_python),
            "-I",
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--no-deps",
            "-r",
            str(requirements),
        ],
    ]


def test_windows_build_environment_accepts_versioned_base_executable_alias(
    tmp_path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    requirements = repo_root / sdk_build_support.SDK_BUILD_REQUIREMENTS_RELATIVE
    requirements.parent.mkdir(parents=True)
    requirements.write_text("pip==26.1.2\n", encoding="utf-8")
    environment_root = repo_root / "build" / "python-runtime" / "build-env"
    build_python = environment_root / "Scripts" / "python.exe"
    build_python.parent.mkdir(parents=True)
    build_python.touch()
    (environment_root / "python-sdk-build-requirements.txt").write_bytes(requirements.read_bytes())
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    python_alias = runtime_root / "python.exe"
    canonical_python = runtime_root / "python3.14t.exe"
    python_alias.touch()
    canonical_python.touch()

    monkeypatch.setattr(sdk_build_support, "_is_windows", lambda: True)
    monkeypatch.setattr(
        sdk_build_support,
        "_python_version_and_paths",
        lambda python: {
            "version": "3.14",
            "soabi": "cp314t-win_amd64",
            "free_threaded": True,
            "py_gil_disabled": True,
            "base_prefix": str(runtime_root),
            "base_executable": str(canonical_python if Path(python) == build_python else python_alias),
        },
    )
    commands = []
    monkeypatch.setattr(
        sdk_build_support,
        "_run",
        lambda command, **_kwargs: commands.append(command) or 0,
    )
    monkeypatch.setattr(sdk_build_support, "_python_pip_error", lambda _python: None)

    result = sdk_build_support._ensure_sdk_python_build_environment(
        repo_root,
        base_python=python_alias,
    )

    assert result == build_python
    assert commands == []


def test_target_metadata_cleanup_keeps_entry_point_discovery_deterministic(tmp_path):
    target_dir = tmp_path / "site-packages"
    target_dir.mkdir()
    old_metadata = target_dir / "termin_voxels-0.1.0+old.dist-info"
    old_metadata.mkdir()
    (old_metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: termin-voxels\nVersion: 0.1.0+old\n",
        encoding="utf-8",
    )
    package = PackageEntry("termin-voxels", "termin-voxels", (), ())

    sdk_runtime_metadata._clear_target_python_package_metadata(target_dir, [package])

    fresh_metadata = target_dir / "termin_voxels-0.1.0+fresh.dist-info"
    fresh_metadata.mkdir()
    (fresh_metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: termin-voxels\nVersion: 0.1.0+fresh\n",
        encoding="utf-8",
    )
    (fresh_metadata / "entry_points.txt").write_text(
        "[termin.asset_import_plugins]\nvoxel_grid = termin.default_assets.voxels.asset_plugin:create_import_plugin\n",
        encoding="utf-8",
    )

    distributions = [
        distribution
        for distribution in importlib.metadata.distributions(path=[str(target_dir)])
        if distribution.metadata["Name"] == "termin-voxels"
    ]
    entry_points = [
        entry_point
        for distribution in distributions
        for entry_point in distribution.entry_points
        if entry_point.group == "termin.asset_import_plugins"
    ]

    assert len(distributions) == 1
    assert [entry_point.name for entry_point in entry_points] == ["voxel_grid"]


def test_editable_install_is_sequential_and_no_deps(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    (sdk_prefix / "lib").mkdir(parents=True)
    for package_path in ("pkg-a", "pkg-b"):
        (repo_root / package_path).mkdir(parents=True)

    packages = [
        PackageEntry("pkg-a", "pkg-a", (), ()),
        PackageEntry("pkg-b", "pkg-b", (), ()),
    ]
    commands = []

    monkeypatch.setattr(sdk_package_install, "_sdk_packages", lambda _repo_root: packages)
    monkeypatch.setattr(sdk_package_install, "_python_bin", lambda: "python")
    monkeypatch.setattr(
        sdk_package_install,
        "_run",
        lambda command, **_kwargs: commands.append(command) or 0,
    )

    result = sdk_package_install.install_pip_packages(
        repo_root=repo_root,
        sdk_prefix=sdk_prefix,
        build_dir=repo_root / "build" / "Release",
        target_dir=None,
        editable=True,
        force=False,
    )

    assert result == 0
    assert len(commands) == 2
    for command in commands:
        assert command[:5] == [
            "python",
            "-m",
            "pip",
            "install",
            "--no-build-isolation",
        ]
        assert "--no-deps" in command
        assert "-e" in command


def test_editable_install_removes_legacy_source_native_artifacts(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    legacy_dir = repo_root / "editor/termin-app" / "termin"
    legacy_dir.mkdir(parents=True)
    (sdk_prefix / "lib").mkdir(parents=True)
    stale_artifact = legacy_dir / "_native.cp312-win_amd64.pyd"
    stale_artifact.write_text("old binding", encoding="utf-8")
    keep_artifact = legacy_dir / "_editor_native.cp312-win_amd64.pyd"
    keep_artifact.write_text("current binding", encoding="utf-8")

    packages = [PackageEntry("editor/termin-app", "termin-app", (), ())]
    commands = []

    monkeypatch.setattr(sdk_package_install, "_sdk_packages", lambda _repo_root: packages)
    monkeypatch.setattr(sdk_package_install, "_python_bin", lambda: "python")
    monkeypatch.setattr(
        sdk_package_install,
        "_run",
        lambda command, **_kwargs: commands.append(command) or 0,
    )

    result = sdk_package_install.install_pip_packages(
        repo_root=repo_root,
        sdk_prefix=sdk_prefix,
        build_dir=repo_root / "build" / "Release",
        target_dir=None,
        editable=True,
        force=False,
    )

    assert result == 0
    assert not stale_artifact.exists()
    assert keep_artifact.is_file()
    assert len(commands) == 1


def test_editable_install_failure_reports_windows_native_lock_context(
    tmp_path,
    monkeypatch,
    capsys,
):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    package_root = repo_root / "engine/termin-input"
    native_dir = package_root / "python" / "termin" / "input"
    native_dir.mkdir(parents=True)
    (sdk_prefix / "lib").mkdir(parents=True)
    native_artifact = native_dir / "_input_native.cp310-win_amd64.pyd"
    native_artifact.write_text("native", encoding="utf-8")

    packages = [PackageEntry("engine/termin-input", "termin-input", (), ())]

    monkeypatch.setattr(sdk_package_install, "_sdk_packages", lambda _repo_root: packages)
    monkeypatch.setattr(sdk_package_install, "_python_bin", lambda: "python")
    monkeypatch.setattr(sdk_package_install, "_is_windows", lambda: True)
    monkeypatch.setattr(
        sdk_package_install,
        "_run",
        lambda _command, **_kwargs: 1,
    )
    monkeypatch.setattr(
        sdk_package_install,
        "_windows_module_users",
        lambda module_name: [f"python.exe 123 Console 1 100 K {module_name}"],
    )
    monkeypatch.setattr(
        sdk_package_install,
        "_windows_python_processes",
        lambda: ["python.exe 123 Console 1 100 K"],
    )

    result = sdk_package_install.install_pip_packages(
        repo_root=repo_root,
        sdk_prefix=sdk_prefix,
        build_dir=repo_root / "build" / "Release",
        target_dir=None,
        editable=True,
        force=False,
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "pip install failed for termin-input (1/1)" in captured.err
    assert "Python package sync stopped" in captured.err
    assert str(native_artifact) in captured.err
    assert "python.exe 123" in captured.err
    assert "install-pip-packages.ps1 --editable --force" in captured.err


@pytest.mark.parametrize(
    ("is_windows", "bundled_python_parts"),
    [
        (False, ("lib", "python3.10")),
        (True, ("python", "Lib")),
    ],
)
def test_sdk_python_install_builds_wheels_then_installs_offline_and_writes_manifest(
    tmp_path,
    monkeypatch,
    is_windows,
    bundled_python_parts,
):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    build_dir = repo_root / "build" / "Release"
    bundled_py_dir = sdk_prefix.joinpath(*bundled_python_parts)
    source_stdlib = tmp_path / "host" / "stdlib"
    (source_stdlib / "ensurepip").mkdir(parents=True)
    (source_stdlib / "os.py").write_text("", encoding="utf-8")
    site_packages = bundled_py_dir / "site-packages"
    (bundled_py_dir / "ensurepip").mkdir(parents=True)
    installed_artifact = site_packages / "example" / "_example_native.pyd"
    installed_artifact.parent.mkdir(parents=True)
    installed_artifact.write_bytes(b"installed")
    (sdk_prefix / "lib").mkdir(exist_ok=True)
    (build_dir / "bin").mkdir(parents=True)
    if is_windows:
        (tmp_path / "unused").mkdir()
        (tmp_path / "unused" / "python310.lib").write_bytes(b"import")
    else:
        (sdk_prefix / "lib" / "libpython3.10.so").write_bytes(b"shared")

    calls = []

    monkeypatch.setattr(sdk_python_install, "_active_sdk_profile", lambda _root: FULL_SDK_PROFILE)
    monkeypatch.setattr(sdk_python_install, "_sdk_packages", lambda _root: [])
    monkeypatch.setattr(sdk_python_install, "_sdk_application_payloads", lambda _root: [])
    monkeypatch.setattr(sdk_python_install, "_installed_core_input", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sdk_python_install, "_is_windows", lambda: is_windows)
    monkeypatch.setattr(sdk_bundled_python, "_is_windows", lambda: is_windows)
    monkeypatch.setattr(sdk_python_layout, "_is_windows", lambda: is_windows)
    monkeypatch.setattr(sdk_python_install, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_python_install,
        "_python_version_and_paths",
        lambda _py_exec: {
            "version": "3.10",
            "soabi": "cpython-310-x86_64-linux-gnu",
            "free_threaded": False,
            "py_gil_disabled": False,
            "stdlib": str(source_stdlib),
            "libdir": str(tmp_path / "unused"),
            "ldlibrary": "python310.dll" if is_windows else "libpython3.10.so",
            "sitepackages": [],
        },
    )
    monkeypatch.setattr(
        sdk_python_install,
        "ensure_bundled_python_cli",
        lambda _sdk_prefix, **_kwargs: None,
    )
    monkeypatch.setattr(
        sdk_bundled_python,
        "_python_version_and_paths",
        sdk_python_install._python_version_and_paths,
    )
    monkeypatch.setattr(
        sdk_python_install,
        "_ensure_sdk_python_build_environment",
        lambda _root, **_kwargs: Path("build-python"),
    )
    monkeypatch.setattr(
        sdk_python_install,
        "_runtime_wheel_dirs",
        lambda _root: (Path("external"), Path("local")),
    )
    monkeypatch.setattr(
        sdk_python_install,
        "_prepare_external_runtime_wheels",
        lambda root, wheels, python: calls.append(("external", root, wheels, python)) or 0,
    )
    monkeypatch.setattr(
        sdk_python_install,
        "_build_local_package_wheels",
        lambda **kwargs: calls.append(("build", kwargs, installed_artifact.is_file())) or 0,
    )
    monkeypatch.setattr(
        sdk_python_install,
        "_install_prepared_runtime_wheels",
        lambda **kwargs: calls.append(("install", kwargs)) or 0,
    )
    monkeypatch.setattr(
        sdk_python_install,
        "install_application_payloads",
        lambda **_kwargs: Path("application-manifest"),
    )
    monkeypatch.setattr(
        sdk_python_install,
        "write_python_runtime_manifest",
        lambda *args, **_kwargs: calls.append(("manifest", args)) or Path("manifest"),
    )

    result = sdk_python_install.install_python_packages(
        repo_root=repo_root,
        sdk_prefix=sdk_prefix,
        build_dir=build_dir,
    )

    assert result == 0
    assert [call[0] for call in calls] == ["external", "build", "install", "manifest"]
    assert calls[1][2] is True
    assert calls[2][1]["site_packages"] == site_packages
    assert calls[2][1]["external_wheels"] == Path("external")
    assert calls[2][1]["local_wheels"] == Path("local")
    assert calls[3][1] == (repo_root, sdk_prefix, site_packages)


def test_install_packages_rejects_unknown_options(capsys):
    result = sdk.main(
        [
            "--repo-root",
            str(sdk.repo_root_from(Path(__file__))),
            "install-packages",
            "--unknown-option",
        ]
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "unknown install-packages option" in captured.err
