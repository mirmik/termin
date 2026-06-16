"""Package the desktop runtime payload into a Termin desktop bundle."""

from __future__ import annotations

import importlib.metadata
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from termin.project_build.runtime_package_exporter import RuntimePackageExportDiagnostic


@dataclass
class DesktopRuntimeBundleResult:
    sdk_root: Path | None
    bin_dir: Path
    lib_dir: Path
    python_home: Path | None
    diagnostics: list[RuntimePackageExportDiagnostic] = field(default_factory=list)


def package_desktop_runtime(
    dist_dir: str | Path,
    requirements: list[str],
    sdk_root: str | Path | None = None,
) -> DesktopRuntimeBundleResult:
    """Copy the SDK runtime needed by the bundle-local C++ player."""
    dist_dir_path = Path(dist_dir).resolve()
    diagnostics: list[RuntimePackageExportDiagnostic] = []
    resolved_sdk_root = _resolve_sdk_root(sdk_root)

    bin_dir = dist_dir_path / "bin"
    lib_dir = dist_dir_path / "lib"
    python_home: Path | None = None

    if resolved_sdk_root is None:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "runtime",
                "Termin SDK root was not found; desktop runtime was not packaged",
            )
        )
        return DesktopRuntimeBundleResult(
            sdk_root=None,
            bin_dir=bin_dir,
            lib_dir=lib_dir,
            python_home=None,
            diagnostics=diagnostics,
        )

    _replace_dir(bin_dir)
    _replace_dir(lib_dir)

    _copy_player_executable(resolved_sdk_root, bin_dir, diagnostics)
    _copy_native_libraries(resolved_sdk_root, lib_dir, diagnostics)
    python_home = _copy_python_home(resolved_sdk_root, lib_dir, diagnostics)
    _copy_shared_data(resolved_sdk_root, dist_dir_path, diagnostics)

    if python_home is not None:
        site_packages = python_home / "site-packages"
        _copy_requirements(requirements, site_packages, diagnostics)

    return DesktopRuntimeBundleResult(
        sdk_root=resolved_sdk_root,
        bin_dir=bin_dir,
        lib_dir=lib_dir,
        python_home=python_home,
        diagnostics=diagnostics,
    )


def _resolve_sdk_root(sdk_root: str | Path | None) -> Path | None:
    candidates: list[Path] = []
    if sdk_root is not None:
        candidates.append(Path(sdk_root))
    env_sdk = os.environ.get("TERMIN_SDK")
    if env_sdk:
        candidates.append(Path(env_sdk))

    current = Path(__file__).resolve()
    for parent in current.parents:
        candidates.append(parent)
        sdk_child = parent / "sdk"
        if sdk_child.exists():
            candidates.append(sdk_child)

    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / "bin").exists() and (resolved / "lib").exists():
            return resolved
    return None


def _copy_player_executable(
    sdk_root: Path,
    bin_dir: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    names = ["termin_player.exe", "termin_player"]
    for name in names:
        source = sdk_root / "bin" / name
        if source.exists() and source.is_file():
            shutil.copy2(source, bin_dir / source.name)
            return

    diagnostics.append(
        RuntimePackageExportDiagnostic(
            "error",
            "bin/termin_player",
            f"termin_player executable was not found in SDK: {sdk_root / 'bin'}",
        )
    )


def _copy_native_libraries(
    sdk_root: Path,
    lib_dir: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    source_lib_dir = sdk_root / "lib"
    if not source_lib_dir.exists():
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "lib",
                f"SDK lib directory was not found: {source_lib_dir}",
            )
        )
        return

    patterns = ["*.so", "*.so.*", "*.dylib", "*.dll"]
    copied: set[Path] = set()
    for pattern in patterns:
        for source in source_lib_dir.glob(pattern):
            if not source.is_file():
                continue
            target = lib_dir / source.name
            if target in copied:
                continue
            shutil.copy2(source, target)
            copied.add(target)

    if len(copied) == 0:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "lib",
                f"No native libraries were found in SDK lib directory: {source_lib_dir}",
            )
        )


def _copy_python_home(
    sdk_root: Path,
    lib_dir: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> Path | None:
    source_lib_dir = sdk_root / "lib"
    python_homes = sorted(
        path
        for path in source_lib_dir.iterdir()
        if path.is_dir() and path.name.startswith("python3.") and (path / "os.py").exists()
    )
    if not python_homes:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "lib/python",
                f"Bundled Python stdlib was not found in SDK: {source_lib_dir}",
            )
        )
        return None

    source = python_homes[0]
    target = lib_dir / source.name
    _copytree_clean(source, target)
    _copy_sdk_python_overlay(sdk_root, target / "site-packages")
    return target


def _copy_sdk_python_overlay(sdk_root: Path, site_packages: Path) -> None:
    source = sdk_root / "lib" / "python"
    if not source.exists():
        return
    site_packages.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = site_packages / child.name
        if child.is_dir():
            _copytree_merge_clean(child, target)
        elif child.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, target)


def _copy_shared_data(
    sdk_root: Path,
    dist_dir: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    source = sdk_root / "share" / "termin"
    if not source.exists():
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "warning",
                "share/termin",
                f"SDK shared data directory was not found: {source}",
            )
        )
        return

    target = dist_dir / "share" / "termin"
    _copytree_clean(source, target)


def _copy_requirements(
    requirements: list[str],
    site_packages: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    pending = sorted(set(requirements))
    copied: set[str] = set()

    while pending:
        requirement = pending.pop(0)
        package_name = _requirement_distribution_name(requirement)
        if package_name == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    "python/requirements",
                    f"Invalid Python requirement name: {requirement}",
                )
            )
            continue

        normalized = _normalize_distribution_name(package_name)
        if normalized in copied:
            continue
        copied.add(normalized)

        try:
            distribution = importlib.metadata.distribution(package_name)
        except importlib.metadata.PackageNotFoundError:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    "python/requirements",
                    f"Python requirement is not installed in the build environment: {requirement}",
                )
            )
            continue

        files = distribution.files
        if files is None:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    "python/requirements",
                    f"Python requirement has no file list and cannot be copied: {requirement}",
                )
            )
            continue

        for file in files:
            source = Path(distribution.locate_file(file))
            if not source.is_file():
                continue
            target = site_packages / Path(file)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        for required in distribution.requires or []:
            required_name = _requirement_distribution_name(required)
            if required_name and _normalize_distribution_name(required_name) not in copied:
                pending.append(required_name)


def _requirement_distribution_name(requirement: str) -> str:
    text = requirement.split(";", 1)[0].strip()
    if " " in text:
        text = text.split(" ", 1)[0]
    for separator in ("==", ">=", "<=", "~=", "!=", ">", "<", "["):
        if separator in text:
            text = text.split(separator, 1)[0]
    return text.strip()


def _normalize_distribution_name(name: str) -> str:
    return name.lower().replace("_", "-")


def _replace_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _copytree_clean(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        source,
        target,
        symlinks=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )


def _copytree_merge_clean(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        if child.name == "__pycache__" or child.suffix in {".pyc", ".pyo"}:
            continue
        child_target = target / child.name
        if child.is_dir():
            _copytree_merge_clean(child, child_target)
        elif child.is_file():
            child_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, child_target)
