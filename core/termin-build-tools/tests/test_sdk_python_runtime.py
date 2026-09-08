import json
from pathlib import Path

import pytest

from termin_build import (
    sdk,
    sdk_bundled_python,
    sdk_native_artifacts,
    sdk_python_install,
    sdk_python_layout,
    sdk_runtime_metadata,
    sdk_verification,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
FULL_SDK_PROFILE = sdk.load_sdk_profiles(REPO_ROOT).profile("full")


def test_python_interpreter_rejects_conflicting_overrides(tmp_path, monkeypatch):
    first = tmp_path / "python-a"
    second = tmp_path / "python-b"
    first.write_text("", encoding="utf-8")
    second.write_text("", encoding="utf-8")
    monkeypatch.setenv("PYTHON_BIN", str(first))
    monkeypatch.setenv("PYTHON_EXECUTABLE", str(second))

    with pytest.raises(RuntimeError, match="different interpreters"):
        sdk_python_layout._python_executable()


def test_verify_sdk_python_launcher_rejects_missing_launcher(tmp_path, capsys):
    sdk_prefix = tmp_path / "sdk"

    assert sdk.verify_sdk_python_launcher(sdk_prefix, import_roots=("termin.base",)) == 1
    assert "SDK Python launcher is missing" in capsys.readouterr().err


@pytest.mark.parametrize("is_windows", [False, True])
def test_verify_sdk_python_launcher_checks_platform_layout_isolation_and_imports(
    tmp_path,
    monkeypatch,
    is_windows,
):
    sdk_prefix = tmp_path / "sdk"
    python_home = sdk_prefix / "python" if is_windows else sdk_prefix
    launcher_name = "termin_python.exe" if is_windows else "termin_python"
    launcher = sdk_prefix / "bin" / launcher_name
    launcher.parent.mkdir(parents=True)
    launcher.write_text("launcher", encoding="utf-8")
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        if "--termin-info" in command:
            return sdk.subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "sdk_root": str(sdk_prefix.resolve()),
                        "python_home": str(python_home.resolve()),
                        "isolated": True,
                        "use_environment": False,
                        "user_site": False,
                    }
                ),
                stderr="",
            )
        return sdk.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(sdk_verification, "_is_windows", lambda: is_windows)
    monkeypatch.setattr(sdk.subprocess, "run", fake_run)

    assert sdk.verify_sdk_python_launcher(sdk_prefix, import_roots=("termin.base", "termin.engine")) == 0
    assert len(commands) == 2
    assert "termin.engine" in commands[1][0][-1]
    for _command, kwargs in commands:
        assert kwargs["env"]["PYTHONHOME"].endswith("__invalid_python_home__")
        assert kwargs["env"]["PYTHONPATH"].endswith("__invalid_python_path__")


def test_sdk_python_launcher_uses_graphics_smoke_imports(tmp_path, monkeypatch):
    sdk_prefix = tmp_path / "sdk"
    launcher = sdk_prefix / "bin" / "termin_python"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("", encoding="utf-8")
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        if "--termin-info" in command:
            return sdk.subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "sdk_root": str(sdk_prefix.resolve()),
                        "python_home": str(sdk_prefix.resolve()),
                        "isolated": True,
                        "use_environment": False,
                        "user_site": False,
                    }
                ),
                stderr="",
            )
        return sdk.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(sdk_verification, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk.subprocess, "run", fake_run)

    assert (
        sdk.verify_sdk_python_launcher(
            sdk_prefix,
            import_roots=("termin.base", "termin.plot", "termin.visual_scene"),
        )
        == 0
    )
    smoke = commands[1][0][-1]
    assert "termin.plot" in smoke
    assert "termin.visual_scene" in smoke
    assert "termin.engine" not in smoke


def test_installed_artifact_selection_rejects_stale_python_abi(tmp_path):
    package_dir = tmp_path / "python" / "Lib" / "site-packages" / "termin" / "sample"
    package_dir.mkdir(parents=True)
    stale = package_dir / "_sample_native.cp312-win_amd64.pyd"
    expected = package_dir / "_sample_native.cp314t-win_amd64.pyd"
    stale.touch()
    expected.touch()
    python_abi = sdk.PythonAbiIdentity(
        version="3.14",
        soabi="cp314t-win_amd64",
        free_threaded=True,
        py_gil_disabled=True,
    )

    result = sdk_native_artifacts.find_installed_artifact(
        tmp_path,
        "termin.sample._sample_native",
        "_sample_native",
        python_abi=python_abi,
    )

    assert result == expected


def test_bundled_python_runtime_copies_shared_libpython_and_drops_config_artifacts(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    stale_stdlib = sdk_prefix / "lib" / "python3.10" / "removed_in_new_runtime.py"
    stale_stdlib.parent.mkdir(parents=True)
    stale_stdlib.write_text("stale\n", encoding="utf-8")
    preserved_package = sdk_prefix / "lib" / "python3.10" / "site-packages" / "preserved.py"
    preserved_package.parent.mkdir(parents=True)
    preserved_package.write_text("installed\n", encoding="utf-8")
    stdlib = tmp_path / "host" / "lib" / "python3.10"
    include = tmp_path / "host" / "include" / "python3.10"
    libdir = tmp_path / "host" / "lib"
    config_dir = stdlib / "config-3.10-x86_64-linux-gnu"
    config_dir.mkdir(parents=True)
    (config_dir / "libpython3.10.a").write_bytes(b"static")
    (stdlib / "ensurepip").mkdir()
    (stdlib / "ctypes").mkdir()
    (stdlib / "ctypes" / "__init__.py").write_text("", encoding="utf-8")
    include.mkdir(parents=True)
    (include / "Python.h").write_text("/* fixture */\n", encoding="utf-8")
    (libdir / "libpython3.10.so.1.0").write_bytes(b"shared")

    monkeypatch.setattr(sdk_bundled_python, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_bundled_python, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_bundled_python,
        "_python_version_and_paths",
        lambda _py_exec: {
            "version": "3.10",
            "stdlib": str(stdlib),
            "include": str(include),
            "platinclude": str(include),
            "libdir": str(libdir),
            "sitepackages": [],
        },
    )

    bundled_py_dir = sdk_bundled_python.ensure_bundled_python_runtime(sdk_prefix)

    assert bundled_py_dir == sdk_prefix / "lib" / "python3.10"
    assert (sdk_prefix / "lib" / "libpython3.10.so.1.0").read_bytes() == b"shared"
    assert (sdk_prefix / "include" / "python3.10" / "Python.h").read_text(encoding="utf-8") == "/* fixture */\n"
    assert not (bundled_py_dir / "config-3.10-x86_64-linux-gnu").exists()
    assert (bundled_py_dir / "ctypes" / "__init__.py").is_file()
    assert not stale_stdlib.exists()
    assert preserved_package.read_text(encoding="utf-8") == "installed\n"


def test_windows_bundled_python_runtime_copies_exact_development_import_library(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    (sdk_prefix / "lib").mkdir(parents=True)
    (sdk_prefix / "lib" / "python312.lib").write_bytes(b"stale")
    runtime_root = tmp_path / "runtime"
    stdlib = runtime_root / "Lib"
    include = runtime_root / "include"
    libs = runtime_root / "libs"
    stdlib.mkdir(parents=True)
    include.mkdir()
    libs.mkdir()
    (stdlib / "os.py").write_text("", encoding="utf-8")
    (include / "Python.h").write_text("/* fixture */\n", encoding="utf-8")
    (libs / "python314t.lib").write_bytes(b"canonical")
    (libs / "python3t.lib").write_bytes(b"stable-abi")

    monkeypatch.setattr(sdk_bundled_python, "_is_windows", lambda: True)
    monkeypatch.setattr(sdk_bundled_python, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_bundled_python,
        "_python_version_and_paths",
        lambda _py_exec: {
            "version": "3.14",
            "stdlib": str(stdlib),
            "include": str(include),
            "platinclude": str(include),
            "libdir": str(libs),
            "base_prefix": str(runtime_root),
            "prefix": str(runtime_root),
            "ldlibrary": "python314t.dll",
            "free_threaded": True,
            "sitepackages": [],
        },
    )

    bundled_py_dir = sdk_bundled_python.ensure_bundled_python_runtime(sdk_prefix)

    assert bundled_py_dir == sdk_prefix / "python" / "Lib"
    assert (sdk_prefix / "lib" / "python314t.lib").read_bytes() == b"canonical"
    assert not (sdk_prefix / "lib" / "python312.lib").exists()
    assert not (sdk_prefix / "lib" / "python3t.lib").exists()


def test_sdk_python_install_repairs_existing_runtime_shared_libpython(
    tmp_path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    build_dir = repo_root / "build" / "Release"
    bundled_py_dir = sdk_prefix / "lib" / "python3.10"
    source_stdlib = tmp_path / "host" / "stdlib"
    (source_stdlib / "ensurepip").mkdir(parents=True)
    (source_stdlib / "os.py").write_text("", encoding="utf-8")
    site_packages = bundled_py_dir / "site-packages"
    host_libdir = tmp_path / "host" / "lib"
    config_dir = bundled_py_dir / "config-3.10-x86_64-linux-gnu"
    (bundled_py_dir / "ensurepip").mkdir(parents=True)
    site_packages.mkdir()
    config_dir.mkdir()
    (config_dir / "libpython3.10.a").write_bytes(b"static")
    host_libdir.mkdir(parents=True)
    (host_libdir / "libpython3.10.so.1.0").write_bytes(b"shared")
    (build_dir / "bin").mkdir(parents=True)

    monkeypatch.setattr(sdk_python_install, "_active_sdk_profile", lambda _root: FULL_SDK_PROFILE)
    monkeypatch.setattr(sdk_python_install, "_sdk_packages", lambda _root: [])
    monkeypatch.setattr(sdk_python_install, "_sdk_application_payloads", lambda _root: [])
    monkeypatch.setattr(sdk_python_install, "_installed_core_input", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sdk_python_install, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_bundled_python, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_runtime_metadata, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_python_install,
        "_python_version_and_paths",
        lambda _py_exec: {
            "version": "3.10",
            "soabi": "cpython-310-x86_64-linux-gnu",
            "free_threaded": False,
            "py_gil_disabled": False,
            "stdlib": str(source_stdlib),
            "libdir": str(host_libdir),
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
    monkeypatch.setattr(sdk_python_install, "_prepare_external_runtime_wheels", lambda *_args: 0)
    monkeypatch.setattr(sdk_python_install, "_build_local_package_wheels", lambda **_kwargs: 0)
    monkeypatch.setattr(sdk_python_install, "_install_prepared_runtime_wheels", lambda **_kwargs: 0)
    monkeypatch.setattr(
        sdk_python_install,
        "install_application_payloads",
        lambda **_kwargs: Path("application-manifest"),
    )
    monkeypatch.setattr(
        sdk_python_install,
        "write_python_runtime_manifest",
        lambda *_args, **_kwargs: Path("manifest"),
    )

    result = sdk_python_install.install_python_packages(
        repo_root=repo_root,
        sdk_prefix=sdk_prefix,
        build_dir=build_dir,
    )

    assert result == 0
    assert (sdk_prefix / "lib" / "libpython3.10.so.1.0").read_bytes() == b"shared"
    assert not config_dir.exists()


def test_prepare_build_python_runtime_sanitizes_sdk_before_cmake(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    bundled_py_dir = sdk_prefix / "lib" / "python3.14"
    config_dir = bundled_py_dir / "config-3.14-x86_64-linux-gnu"
    host_libdir = tmp_path / "host" / "lib"
    config_dir.mkdir(parents=True)
    (bundled_py_dir / "ensurepip").mkdir()
    (bundled_py_dir / "os.py").write_text("", encoding="utf-8")
    (config_dir / "libpython3.14.a").write_bytes(b"static")
    host_libdir.mkdir(parents=True)
    (host_libdir / "libpython3.14.so").write_bytes(b"shared")

    monkeypatch.setattr(sdk_python_install, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_bundled_python, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_python_install, "_python_executable", lambda: "python")
    monkeypatch.setattr(sdk_bundled_python, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_python_install,
        "_python_version_and_paths",
        lambda _py_exec: {
            "version": "3.14",
            "soabi": "cpython-314-x86_64-linux-gnu",
            "free_threaded": False,
            "py_gil_disabled": False,
            "stdlib": str(tmp_path / "unused"),
            "libdir": str(host_libdir),
            "sitepackages": [],
        },
    )
    monkeypatch.setattr(
        sdk_bundled_python,
        "_python_version_and_paths",
        sdk_python_install._python_version_and_paths,
    )

    result = sdk_python_install.prepare_build_python_runtime(sdk_prefix)

    assert result == 0
    assert not config_dir.exists()
    assert (sdk_prefix / "lib" / "libpython3.14.so").read_bytes() == b"shared"


def test_prepare_build_python_runtime_copies_windows_runtime_for_consumers(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    bundled_py_dir = sdk_prefix / "python" / "Lib"
    calls = []

    monkeypatch.setattr(sdk_python_install, "_is_windows", lambda: True)
    monkeypatch.setattr(sdk_python_install, "_python_executable", lambda: "python")
    runtime_info = {
        "version": "3.14",
        "soabi": "cp314t-win_amd64",
        "free_threaded": True,
        "py_gil_disabled": True,
    }
    monkeypatch.setattr(
        sdk_python_install,
        "_python_version_and_paths",
        lambda _py_exec: runtime_info,
    )
    monkeypatch.setattr(
        sdk_python_install,
        "ensure_bundled_python_runtime",
        lambda prefix, **kwargs: calls.append((prefix, kwargs)) or bundled_py_dir,
    )

    result = sdk_python_install.prepare_build_python_runtime(sdk_prefix)

    assert result == 0
    assert calls == [
        (
            sdk_prefix,
            {
                "python_executable": Path("python"),
                "runtime_info": runtime_info,
            },
        ),
    ]


def test_prepare_build_python_runtime_rejects_unsupported_python_without_mutation(
    tmp_path,
    monkeypatch,
    capsys,
):
    sdk_prefix = tmp_path / "sdk"
    bundled_py_dir = sdk_prefix / "lib" / "python3.14t"
    (bundled_py_dir / "site-packages").mkdir(parents=True)
    (bundled_py_dir / "os.py").write_bytes(b"existing stdlib\n")
    (bundled_py_dir / "site-packages" / "installed.py").write_bytes(b"existing package\n")
    (sdk_prefix / "lib" / "libpython3.14t.so.1.0").write_bytes(b"existing shared library")
    header = sdk_prefix / "include" / "python3.14t" / "Python.h"
    header.parent.mkdir(parents=True)
    header.write_bytes(b"existing header\n")

    host_root = tmp_path / "host"
    host_stdlib = host_root / "lib" / "python3.10"
    host_include = host_root / "include" / "python3.10"
    (host_stdlib / "ensurepip").mkdir(parents=True)
    (host_stdlib / "os.py").write_bytes(b"unsupported stdlib\n")
    host_include.mkdir(parents=True)
    (host_include / "Python.h").write_bytes(b"unsupported header\n")
    (host_root / "lib" / "libpython3.10.so.1.0").write_bytes(b"unsupported shared library")
    unsupported_info = {
        "version": "3.10",
        "soabi": "cpython-310-x86_64-linux-gnu",
        "free_threaded": False,
        "py_gil_disabled": False,
        "stdlib": str(host_stdlib),
        "include": str(host_include),
        "platinclude": str(host_include),
        "libdir": str(host_root / "lib"),
        "sitepackages": [],
    }

    def snapshot() -> dict[str, bytes | None]:
        return {
            path.relative_to(sdk_prefix).as_posix(): (None if path.is_dir() else path.read_bytes())
            for path in sorted(sdk_prefix.rglob("*"))
        }

    before = snapshot()
    monkeypatch.setattr(sdk_python_install, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_bundled_python, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_python_install, "_python_executable", lambda: "python3.10")
    monkeypatch.setattr(
        sdk_python_install,
        "_python_version_and_paths",
        lambda _py_exec: unsupported_info,
    )
    monkeypatch.setattr(
        sdk_bundled_python,
        "_python_version_and_paths",
        lambda _py_exec: unsupported_info,
    )

    result = sdk_python_install.prepare_build_python_runtime(sdk_prefix)

    assert result == 1
    assert snapshot() == before
    error = capsys.readouterr().err
    assert "failed to validate SDK build Python" in error
    assert "got Python 3.10 with ABI cp310" in error


def test_prepare_build_python_runtime_creates_runtime_for_clean_sdk(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    stdlib = tmp_path / "host" / "lib" / "python3.14"
    host_libdir = tmp_path / "host" / "lib"
    (stdlib / "ensurepip").mkdir(parents=True)
    (stdlib / "os.py").write_text("", encoding="utf-8")
    (host_libdir / "libpython3.14.so").write_bytes(b"shared")

    monkeypatch.setattr(sdk_python_install, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_bundled_python, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_python_install, "_python_executable", lambda: "python")
    monkeypatch.setattr(sdk_bundled_python, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_python_install,
        "_python_version_and_paths",
        lambda _py_exec: {
            "version": "3.14",
            "soabi": "cpython-314-x86_64-linux-gnu",
            "free_threaded": False,
            "py_gil_disabled": False,
            "stdlib": str(stdlib),
            "libdir": str(host_libdir),
            "sitepackages": [],
        },
    )
    monkeypatch.setattr(
        sdk_bundled_python,
        "_python_version_and_paths",
        sdk_python_install._python_version_and_paths,
    )

    result = sdk_python_install.prepare_build_python_runtime(sdk_prefix)

    assert result == 0
    assert (sdk_prefix / "lib" / "python3.14" / "os.py").is_file()
    assert (sdk_prefix / "lib" / "python3.14" / "site-packages").is_dir()
    assert (sdk_prefix / "lib" / "libpython3.14.so").read_bytes() == b"shared"


def test_prepare_build_python_runtime_migrates_to_free_threaded_layout(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    stale_runtime = sdk_prefix / "lib" / "python3.10"
    stale_runtime.mkdir(parents=True)
    stdlib = tmp_path / "host" / "lib" / "python3.14t"
    host_libdir = tmp_path / "host" / "lib"
    (stdlib / "ensurepip").mkdir(parents=True)
    (stdlib / "os.py").write_text("", encoding="utf-8")
    (host_libdir / "libpython3.14t.so").write_bytes(b"shared")

    monkeypatch.setattr(sdk_python_install, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_bundled_python, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_python_install, "_python_executable", lambda: "python")
    monkeypatch.setattr(sdk_bundled_python, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_python_install,
        "_python_version_and_paths",
        lambda _py_exec: {
            "version": "3.14",
            "soabi": "cpython-314t-x86_64-linux-gnu",
            "free_threaded": True,
            "py_gil_disabled": True,
            "stdlib": str(stdlib),
            "libdir": str(host_libdir),
            "sitepackages": [],
        },
    )
    monkeypatch.setattr(
        sdk_bundled_python,
        "_python_version_and_paths",
        sdk_python_install._python_version_and_paths,
    )

    result = sdk_python_install.prepare_build_python_runtime(sdk_prefix)

    assert result == 0
    assert not stale_runtime.exists()
    assert (sdk_prefix / "lib" / "python3.14t" / "os.py").is_file()
    assert (sdk_prefix / "lib" / "python3.14t" / "site-packages").is_dir()
    assert (sdk_prefix / "lib" / "libpython3.14t.so").read_bytes() == b"shared"


def test_sdk_python_layout_rejects_multiple_runtime_abis(tmp_path, monkeypatch):
    sdk_prefix = tmp_path / "sdk"
    (sdk_prefix / "lib" / "python3.10" / "site-packages").mkdir(parents=True)
    (sdk_prefix / "lib" / "python3.12" / "site-packages").mkdir(parents=True)

    monkeypatch.setattr(sdk_python_layout, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_python_layout, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_python_layout,
        "_python_version_and_paths",
        lambda _py_exec: {"version": "3.10"},
    )

    with pytest.raises(RuntimeError, match="multiple bundled Python runtimes"):
        sdk.resolve_sdk_python_layout(sdk_prefix)


def test_sdk_python_layout_rejects_active_python_abi_mismatch(tmp_path, monkeypatch):
    sdk_prefix = tmp_path / "sdk"
    (sdk_prefix / "lib" / "python3.12" / "site-packages").mkdir(parents=True)

    monkeypatch.setattr(sdk_python_layout, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_python_layout, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_python_layout,
        "_python_version_and_paths",
        lambda _py_exec: {"version": "3.10"},
    )

    with pytest.raises(RuntimeError, match="SDK Python ABI mismatch"):
        sdk.resolve_sdk_python_layout(sdk_prefix)


def test_sdk_python_layout_resolves_free_threaded_stdlib_suffix(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    site_packages = sdk_prefix / "lib" / "python3.14t" / "site-packages"
    site_packages.mkdir(parents=True)

    monkeypatch.setattr(sdk_python_layout, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_python_layout, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_python_layout,
        "_python_version_and_paths",
        lambda _py_exec: {
            "version": "3.14",
            "free_threaded": True,
        },
    )

    assert sdk.resolve_sdk_python_layout(sdk_prefix) == site_packages


def test_sdk_python_layout_can_require_native_bindings(tmp_path, monkeypatch):
    sdk_prefix = tmp_path / "sdk"
    termin_base_dir = sdk_prefix / "lib" / "python3.10" / "site-packages" / "termin" / "base"
    termin_base_dir.mkdir(parents=True)

    monkeypatch.setattr(sdk_python_layout, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_python_layout, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_python_layout,
        "_python_version_and_paths",
        lambda _py_exec: {"version": "3.10"},
    )

    with pytest.raises(RuntimeError, match="native bindings were not found"):
        sdk.resolve_sdk_python_layout(sdk_prefix, require_native_bindings=True)

    (termin_base_dir / "_base_native.cpython-310-x86_64-linux-gnu.so").touch()
    assert (
        sdk.resolve_sdk_python_layout(
            sdk_prefix,
            require_native_bindings=True,
        )
        == termin_base_dir.parents[1]
    )


def test_publish_cmake_python_install_normalizes_staged_bindings(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    install_dir = tmp_path / "install"
    site_packages = sdk_prefix / "lib" / "python3.10" / "site-packages"
    legacy_termin_base = install_dir / "lib" / "python" / "termin" / "base"
    staged_package = install_dir / "lib" / "python3.10" / "site-packages" / "termin" / "editor"
    site_packages.mkdir(parents=True)
    legacy_termin_base.mkdir(parents=True)
    staged_package.mkdir(parents=True)
    native_name = "_base_native.cpython-310-x86_64-linux-gnu.so"
    (legacy_termin_base / native_name).write_bytes(b"native")
    (legacy_termin_base / "__init__.py").write_text("", encoding="utf-8")
    cache_dir = legacy_termin_base / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "__init__.cpython-310.pyc").write_bytes(b"bytecode")
    (staged_package / "runtime.py").write_text("VALUE = 1\n", encoding="utf-8")

    monkeypatch.setattr(sdk_python_layout, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_python_layout, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_python_layout,
        "_python_version_and_paths",
        lambda _py_exec: {"version": "3.10"},
    )

    result = sdk.publish_cmake_python_install(install_dir, sdk_prefix)

    assert result == site_packages
    assert (site_packages / "termin" / "base" / native_name).read_bytes() == b"native"
    assert (site_packages / "termin" / "editor" / "runtime.py").read_text() == ("VALUE = 1\n")
    assert not (sdk_prefix / "lib" / "python").exists()
    assert not list(site_packages.rglob("__pycache__"))
    assert not list(site_packages.rglob("*.pyc"))


def test_publish_cmake_python_modules_only_needs_no_bundled_runtime(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    install_dir = tmp_path / "install"
    staged_termin_base = install_dir / "lib" / "python" / "termin" / "base"
    staged_termin_base.mkdir(parents=True)
    native_name = "_base_native.cpython-314t-x86_64-linux-gnu.so"
    (staged_termin_base / native_name).write_bytes(b"native")

    monkeypatch.setattr(sdk_python_layout, "_is_windows", lambda: False)
    monkeypatch.setattr(sdk_python_layout, "_python_executable", lambda: "python")
    monkeypatch.setattr(
        sdk_python_layout,
        "_python_version_and_paths",
        lambda _py_exec: {"version": "3.14", "free_threaded": True},
    )

    result = sdk.publish_cmake_python_install(
        install_dir,
        sdk_prefix,
        modules_only=True,
    )

    expected = sdk_prefix / "lib" / "python3.14t" / "site-packages"
    assert result == expected
    assert (expected / "termin" / "base" / native_name).read_bytes() == b"native"


def test_publish_cmake_python_install_removes_windows_legacy_tree(
    tmp_path,
    monkeypatch,
):
    sdk_prefix = tmp_path / "sdk"
    site_packages = sdk_prefix / "python" / "Lib" / "site-packages"
    termin_base_dir = site_packages / "termin" / "base"
    legacy_package = sdk_prefix / "lib" / "python" / "termin" / "sample"
    termin_base_dir.mkdir(parents=True)
    legacy_package.mkdir(parents=True)
    (termin_base_dir / "_base_native.cp310-win_amd64.pyd").write_bytes(b"native")
    (legacy_package / "_sample_native.cp310-win_amd64.pyd").write_bytes(b"sample")

    monkeypatch.setattr(sdk_python_layout, "_is_windows", lambda: True)
    monkeypatch.setattr(sdk_python_layout, "_python_executable", lambda: "python.exe")
    monkeypatch.setattr(
        sdk_python_layout,
        "_python_version_and_paths",
        lambda _py_exec: {"version": "3.10"},
    )

    result = sdk.publish_cmake_python_install(sdk_prefix, sdk_prefix)

    assert result == site_packages
    assert (site_packages / "termin" / "sample" / "_sample_native.cp310-win_amd64.pyd").read_bytes() == b"sample"
    assert not (sdk_prefix / "lib" / "python").exists()
