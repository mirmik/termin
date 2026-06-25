"""Package the desktop runtime payload into a Termin desktop bundle."""

from __future__ import annotations

import importlib.metadata
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from termin.project_build.runtime_package_exporter import RuntimePackageExportDiagnostic


MINIMAL_PYTHON_PACKAGE_POLICY = "minimal_strict"
SDK_BROAD_COPY_PYTHON_PACKAGE_POLICY = "sdk_broad_copy"
SUPPORTED_PYTHON_PACKAGE_POLICIES = (
    MINIMAL_PYTHON_PACKAGE_POLICY,
    SDK_BROAD_COPY_PYTHON_PACKAGE_POLICY,
)

TERMIN_PLAYER_RUNTIME_DISTRIBUTIONS = (
    "termin-app",
    "termin-nanobind",
    "tcbase",
    "termin-assets",
    "termin-default-assets",
    "termin-prefab",
    "termin-glb",
    "termin-tween",
    "termin-components-tween",
    "termin-audio",
    "termin-voxels",
    "termin-components-voxels",
    "termin-components-physics",
    "termin-components-ui",
    "termin-materials",
    "termin-render-passes",
    "termin-modules",
    "termin-scene",
    "termin-display",
    "termin-engine",
    "termin-render",
    "termin-components-render",
    "termin-input",
    "termin-inspect",
    "termin-collision",
    "termin-physics",
    "termin-navmesh",
    "termin-lighting",
    "tmesh",
    "tgfx",
    "tcgui",
    "numpy",
)

@dataclass(frozen=True)
class PythonBundledDistribution:
    name: str
    version: str
    source: str


@dataclass
class DesktopRuntimeBundleResult:
    sdk_root: Path | None
    bin_dir: Path
    lib_dir: Path
    launcher_path: Path | None
    python_home: Path | None
    python_site_packages: Path | None = None
    python_runtime_manifest_path: Path | None = None
    python_package_policy: str = MINIMAL_PYTHON_PACKAGE_POLICY
    bundled_distributions: list[PythonBundledDistribution] = field(default_factory=list)
    diagnostics: list[RuntimePackageExportDiagnostic] = field(default_factory=list)


@dataclass
class _PythonRuntimeCopyResult:
    home: Path
    site_packages: Path


@dataclass(frozen=True)
class _PendingPythonRequirement:
    requirement: Requirement
    source_text: str
    marker_contexts: frozenset[str]

    @property
    def distribution_name(self) -> str:
        return self.requirement.name

    @property
    def requested_extras(self) -> frozenset[str]:
        return frozenset(_normalize_extra_name(extra) for extra in self.requirement.extras)


def package_desktop_runtime(
    dist_dir: str | Path,
    requirements: list[str],
    app_name: str | None = None,
    sdk_root: str | Path | None = None,
    requirement_search_paths: list[str | Path] | None = None,
    python_package_policy: str = MINIMAL_PYTHON_PACKAGE_POLICY,
) -> DesktopRuntimeBundleResult:
    """Copy the SDK runtime needed by the bundle-local C++ player."""
    dist_dir_path = Path(dist_dir).resolve()
    diagnostics: list[RuntimePackageExportDiagnostic] = []
    resolved_sdk_root = _resolve_sdk_root(sdk_root)
    if python_package_policy not in SUPPORTED_PYTHON_PACKAGE_POLICIES:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "python/package_policy",
                "Unsupported Python package policy: "
                f"{python_package_policy}. Supported policies: "
                + ", ".join(SUPPORTED_PYTHON_PACKAGE_POLICIES),
            )
        )

    bin_dir = dist_dir_path / "bin"
    lib_dir = dist_dir_path / "lib"
    windows_python_home = dist_dir_path / "python"
    launcher_path: Path | None = None
    python_home: Path | None = None
    python_site_packages: Path | None = None
    python_runtime_manifest_path: Path | None = None
    bundled_distributions: list[PythonBundledDistribution] = []

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
            launcher_path=None,
            python_home=None,
            python_site_packages=None,
            python_package_policy=python_package_policy,
            diagnostics=diagnostics,
        )

    _replace_dir(bin_dir)
    _replace_dir(lib_dir)

    launcher_path = _copy_player_executable(
        resolved_sdk_root,
        dist_dir_path,
        app_name or dist_dir_path.name,
        diagnostics,
    )
    _copy_native_libraries(resolved_sdk_root, dist_dir_path, bin_dir, lib_dir, diagnostics)
    python_runtime = _copy_python_home(
        resolved_sdk_root,
        lib_dir,
        windows_python_home,
        diagnostics,
        python_package_policy,
    )
    _copy_shared_data(resolved_sdk_root, dist_dir_path, diagnostics)

    if python_runtime is not None:
        python_home = python_runtime.home
        python_site_packages = python_runtime.site_packages
        search_paths = _runtime_distribution_search_paths(
            resolved_sdk_root,
            _normalize_search_paths(requirement_search_paths),
        )
        if python_package_policy == MINIMAL_PYTHON_PACKAGE_POLICY:
            bundled_distributions.extend(
                _copy_runtime_seed_distributions(
                    python_site_packages,
                    diagnostics,
                    search_paths,
                )
            )
        bundled_distributions.extend(
            _copy_requirements(
                requirements,
                python_site_packages,
                diagnostics,
                search_paths,
            )
        )
        python_runtime_manifest_path = dist_dir_path / "python-runtime.json"
        _write_python_runtime_manifest(
            python_runtime_manifest_path,
            python_runtime,
            python_package_policy,
            bundled_distributions,
        )

    return DesktopRuntimeBundleResult(
        sdk_root=resolved_sdk_root,
        bin_dir=bin_dir,
        lib_dir=lib_dir,
        launcher_path=launcher_path,
        python_home=python_home,
        python_site_packages=python_site_packages,
        python_runtime_manifest_path=python_runtime_manifest_path,
        python_package_policy=python_package_policy,
        bundled_distributions=bundled_distributions,
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
    dist_dir: Path,
    app_name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> Path | None:
    names = ["termin_player.exe", "termin_player"]
    for name in names:
        source = sdk_root / "bin" / name
        if source.exists() and source.is_file():
            target = dist_dir / _desktop_launcher_filename(app_name, source)
            shutil.copy2(source, target)
            return target

    diagnostics.append(
        RuntimePackageExportDiagnostic(
            "error",
            _desktop_launcher_filename(app_name, sdk_root / "bin" / "termin_player"),
            f"termin_player executable was not found in SDK: {sdk_root / 'bin'}",
        )
    )
    return None


def _desktop_launcher_filename(app_name: str, source_executable: Path) -> str:
    stem = _safe_launcher_stem(app_name)
    if source_executable.suffix.lower() == ".exe":
        return f"{stem}.exe"
    return stem


def _safe_launcher_stem(app_name: str) -> str:
    text = app_name.strip()
    if text == "":
        text = "TerminPlayer"

    invalid = set('<>:"/\\|?*')
    result = "".join("_" if ch in invalid or ord(ch) < 32 else ch for ch in text)
    result = result.strip(" .")
    return result or "TerminPlayer"


def _copy_native_libraries(
    sdk_root: Path,
    dist_dir: Path,
    bin_dir: Path,
    lib_dir: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    sdk_bin_target = dist_dir if _is_windows_desktop_sdk_layout(sdk_root) else bin_dir
    source_sets = (
        (sdk_root / "lib", lib_dir, ("*.so", "*.so.*", "*.dylib", "*.dll")),
        (sdk_root / "bin", sdk_bin_target, ("*.dll",)),
    )
    copied: set[Path] = set()
    checked_dirs: list[Path] = []
    for source_dir, target_dir, patterns in source_sets:
        checked_dirs.append(source_dir)
        if not source_dir.exists():
            continue
        for pattern in patterns:
            for source in source_dir.glob(pattern):
                if not source.is_file():
                    continue
                target = target_dir / source.name
                if target in copied:
                    continue
                shutil.copy2(source, target)
                copied.add(target)

    if len(copied) == 0:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "runtime",
                "No native libraries were found in SDK runtime directories: "
                + ", ".join(str(path) for path in checked_dirs),
            )
        )


def _is_windows_desktop_sdk_layout(sdk_root: Path) -> bool:
    return (
        (sdk_root / "bin" / "termin_player.exe").is_file()
        or (sdk_root / "python" / "Lib" / "os.py").is_file()
    )


def _copy_python_home(
    sdk_root: Path,
    lib_dir: Path,
    windows_python_home: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
    python_package_policy: str,
) -> _PythonRuntimeCopyResult | None:
    posix_python_homes = _posix_python_homes(sdk_root)
    windows_python_lib = sdk_root / "python" / "Lib"
    broad_copy = python_package_policy == SDK_BROAD_COPY_PYTHON_PACKAGE_POLICY

    if posix_python_homes:
        source = posix_python_homes[0]
        target = lib_dir / source.name
        _copytree_clean(
            source,
            target,
            ignore_names=set() if broad_copy else _stdlib_copy_ignored_names(),
        )
        site_packages = target / "site-packages"
        site_packages.mkdir(parents=True, exist_ok=True)
        _copy_sdk_python_overlay(sdk_root, site_packages)
        return _PythonRuntimeCopyResult(home=target, site_packages=site_packages)

    if (windows_python_lib / "os.py").is_file():
        _replace_dir(windows_python_home)
        target_lib = windows_python_home / "Lib"
        _copytree_clean(
            windows_python_lib,
            target_lib,
            ignore_names=set() if broad_copy else _stdlib_copy_ignored_names(),
        )
        _copy_windows_python_runtime_support(sdk_root, windows_python_home)
        site_packages = target_lib / "site-packages"
        site_packages.mkdir(parents=True, exist_ok=True)
        _copy_sdk_python_overlay(sdk_root, site_packages)
        return _PythonRuntimeCopyResult(home=windows_python_home, site_packages=site_packages)

    diagnostics.append(
        RuntimePackageExportDiagnostic(
            "error",
            "python",
            "Bundled Python stdlib was not found in SDK runtime directories: "
            f"{sdk_root / 'lib' / 'python'}, {windows_python_lib}",
        )
    )
    return None


def _stdlib_copy_ignored_names() -> set[str]:
    return {
        "site-packages",
        "test",
        "tests",
        "idle_test",
        "turtledemo",
        "lib2to3",
    }


def _copy_windows_python_runtime_support(sdk_root: Path, python_home: Path) -> None:
    source_home = sdk_root / "python"
    for runtime_dir in ("DLLs", "tcl"):
        source = source_home / runtime_dir
        if source.is_dir():
            _copytree_clean(source, python_home / runtime_dir)

    for pattern in ("python.exe", "pythonw.exe", "python*.dll"):
        for source in source_home.glob(pattern):
            if source.is_file():
                shutil.copy2(source, python_home / source.name)


def _posix_python_homes(sdk_root: Path) -> list[Path]:
    source_lib_dir = sdk_root / "lib"
    if not source_lib_dir.is_dir():
        return []
    return sorted(
        path
        for path in source_lib_dir.iterdir()
        if path.is_dir() and path.name.startswith("python3.") and (path / "os.py").exists()
    )


def _copy_sdk_python_overlay(sdk_root: Path, site_packages: Path) -> None:
    for source in _sdk_python_overlays(sdk_root):
        site_packages.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            target = site_packages / child.name
            if child.is_dir():
                _copytree_merge_clean(child, target)
            elif child.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, target)


def _sdk_python_overlays(sdk_root: Path) -> list[Path]:
    candidates = [
        sdk_root / "lib" / "python",
    ]
    return [
        path
        for path in candidates
        if path.exists() and path.is_dir()
    ]


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
    search_paths: list[Path],
) -> list[PythonBundledDistribution]:
    return _copy_distributions(
        requirements,
        site_packages,
        diagnostics,
        search_paths,
        source="project-requirement",
        include_transitive=True,
        missing_is_error=True,
        missing_files_is_error=True,
        allow_environment=True,
    )


def _copy_runtime_seed_distributions(
    site_packages: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
    search_paths: list[Path],
) -> list[PythonBundledDistribution]:
    return _copy_distributions(
        list(TERMIN_PLAYER_RUNTIME_DISTRIBUTIONS),
        site_packages,
        diagnostics,
        search_paths,
        source="termin-runtime",
        include_transitive=True,
        missing_is_error=True,
        missing_files_is_error=True,
        allow_environment=False,
    )



def _copy_distributions(
    requirements: list[str],
    site_packages: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
    search_paths: list[Path],
    *,
    source: str,
    include_transitive: bool,
    missing_is_error: bool,
    missing_files_is_error: bool,
    allow_environment: bool,
) -> list[PythonBundledDistribution]:
    pending: list[_PendingPythonRequirement] = []
    for requirement in sorted(set(requirements)):
        parsed = _parse_pending_requirement(requirement, diagnostics)
        if parsed is not None:
            pending.append(parsed)

    copied: dict[str, importlib.metadata.Distribution] = {}
    processed_dependency_contexts: dict[str, set[str]] = {}
    bundled: list[PythonBundledDistribution] = []

    while pending:
        pending_requirement = pending.pop(0)
        if not _requirement_marker_is_active(
            pending_requirement.requirement,
            pending_requirement.marker_contexts,
        ):
            continue

        package_name = pending_requirement.distribution_name
        normalized = _normalize_distribution_name(package_name)
        distribution = copied.get(normalized)
        if distribution is not None:
            if not _distribution_satisfies_requirement(
                distribution,
                pending_requirement.requirement,
            ):
                _append_incompatible_requirement_diagnostic(
                    pending_requirement,
                    [distribution],
                    diagnostics,
                )
                continue
            if include_transitive:
                _enqueue_unprocessed_dependencies(
                    distribution,
                    pending_requirement,
                    processed_dependency_contexts,
                    pending,
                    diagnostics,
                )
            continue

        distribution = _find_distribution_for_requirement(
            pending_requirement.requirement,
            search_paths,
            allow_environment,
        )
        if distribution is None:
            candidates = _find_distribution_candidates(
                package_name,
                search_paths,
                allow_environment,
            )
            compatible_candidates = [
                candidate
                for candidate in candidates
                if _distribution_satisfies_requirement(
                    candidate,
                    pending_requirement.requirement,
                )
            ]
            if candidates and not compatible_candidates:
                _append_incompatible_requirement_diagnostic(
                    pending_requirement,
                    candidates,
                    diagnostics,
                )
                continue
            if missing_is_error:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        "python/requirements",
                        "Python requirement is not installed in the build environment "
                        "or project requirement paths: "
                        f"{pending_requirement.source_text}",
                    )
                )
            continue

        files = distribution.files
        if files is None:
            if missing_files_is_error:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        "python/requirements",
                        "Python requirement has no file list and cannot be copied: "
                        f"{pending_requirement.source_text}",
                    )
                )
            continue

        for file in files:
            source_file = Path(distribution.locate_file(file))
            if not source_file.is_file():
                continue
            target = site_packages / Path(file)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target)

        bundled.append(
            PythonBundledDistribution(
                name=distribution.metadata.get("Name", package_name),
                version=distribution.version,
                source=source,
            )
        )
        copied[normalized] = distribution

        if include_transitive:
            _enqueue_unprocessed_dependencies(
                distribution,
                pending_requirement,
                processed_dependency_contexts,
                pending,
                diagnostics,
            )

    return bundled


def _parse_pending_requirement(
    requirement: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> _PendingPythonRequirement | None:
    try:
        parsed = Requirement(requirement)
    except InvalidRequirement:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "python/requirements",
                f"Invalid Python requirement: {requirement}",
            )
        )
        return None
    return _PendingPythonRequirement(
        requirement=parsed,
        source_text=requirement,
        marker_contexts=frozenset({""}),
    )


def _parse_dependency_requirement(
    requirement: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> Requirement | None:
    try:
        return Requirement(requirement)
    except InvalidRequirement:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "python/requirements",
                f"Invalid Python dependency metadata requirement: {requirement}",
            )
        )
        return None


def _enqueue_unprocessed_dependencies(
    distribution: importlib.metadata.Distribution,
    pending_requirement: _PendingPythonRequirement,
    processed_dependency_contexts: dict[str, set[str]],
    pending: list[_PendingPythonRequirement],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    normalized = _normalize_distribution_name(pending_requirement.distribution_name)
    requested_contexts = {""}
    requested_contexts.update(pending_requirement.requested_extras)
    processed_contexts = processed_dependency_contexts.setdefault(normalized, set())
    new_contexts = requested_contexts - processed_contexts
    if not new_contexts:
        return
    processed_contexts.update(new_contexts)

    marker_contexts = frozenset(new_contexts)
    for required in distribution.requires or []:
        parsed = _parse_dependency_requirement(required, diagnostics)
        if parsed is None:
            continue
        if not _requirement_marker_is_active(parsed, marker_contexts):
            continue
        pending.append(
            _PendingPythonRequirement(
                requirement=parsed,
                source_text=required,
                marker_contexts=marker_contexts,
            )
        )


def _requirement_marker_is_active(
    requirement: Requirement,
    marker_contexts: frozenset[str],
) -> bool:
    if requirement.marker is None:
        return True
    contexts = marker_contexts or frozenset({""})
    return any(requirement.marker.evaluate({"extra": context}) for context in contexts)


def _distribution_satisfies_requirement(
    distribution: importlib.metadata.Distribution,
    requirement: Requirement,
) -> bool:
    if not requirement.specifier:
        return True
    try:
        version = Version(distribution.version)
    except InvalidVersion:
        return False
    return requirement.specifier.contains(version, prereleases=True)


def _append_incompatible_requirement_diagnostic(
    pending_requirement: _PendingPythonRequirement,
    distributions: list[importlib.metadata.Distribution],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    found_versions = ", ".join(
        f"{distribution.metadata.get('Name', pending_requirement.distribution_name)} "
        f"{distribution.version}"
        for distribution in distributions
    )
    diagnostics.append(
        RuntimePackageExportDiagnostic(
            "error",
            "python/requirements",
            "Installed Python requirement version does not satisfy "
            f"{pending_requirement.source_text}: found {found_versions}",
        )
    )


def _normalize_extra_name(name: str) -> str:
    return str(canonicalize_name(name))


def _normalize_distribution_name(name: str) -> str:
    return str(canonicalize_name(name))


def _normalize_search_paths(paths: list[str | Path] | None) -> list[Path]:
    if paths is None:
        return []
    result: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = Path(path).resolve()
        if resolved in seen or not resolved.is_dir():
            continue
        seen.add(resolved)
        result.append(resolved)
    return result


def _runtime_distribution_search_paths(sdk_root: Path, project_paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    for path in [
        *_sdk_site_packages(sdk_root),
        *project_paths,
    ]:
        if path not in result:
            result.append(path)
    return result


def _sdk_site_packages(sdk_root: Path) -> list[Path]:
    candidates = [sdk_root / "python" / "Lib" / "site-packages"]
    for python_home in _posix_python_homes(sdk_root):
        candidates.append(python_home / "site-packages")
    return [path for path in candidates if path.is_dir()]


def _find_distribution_for_requirement(
    requirement: Requirement,
    search_paths: list[Path],
    allow_environment: bool = True,
) -> importlib.metadata.Distribution | None:
    normalized = _normalize_distribution_name(requirement.name)
    for search_path in search_paths:
        matches = _find_distribution_candidates_in_path(normalized, search_path)
        compatible = [
            distribution
            for distribution in matches
            if _distribution_satisfies_requirement(distribution, requirement)
        ]
        if compatible:
            return _select_best_distribution(compatible)
    if not allow_environment:
        return None
    try:
        distribution = importlib.metadata.distribution(requirement.name)
    except importlib.metadata.PackageNotFoundError:
        return None
    if _distribution_satisfies_requirement(distribution, requirement):
        return distribution
    return None


def _find_distribution_candidates(
    package_name: str,
    search_paths: list[Path],
    allow_environment: bool = True,
) -> list[importlib.metadata.Distribution]:
    normalized = _normalize_distribution_name(package_name)
    candidates: list[importlib.metadata.Distribution] = []
    for search_path in search_paths:
        candidates.extend(_find_distribution_candidates_in_path(normalized, search_path))
    if not allow_environment:
        return candidates
    try:
        candidates.append(importlib.metadata.distribution(package_name))
    except importlib.metadata.PackageNotFoundError:
        pass
    return candidates


def _find_distribution_candidates_in_path(
    normalized_name: str,
    search_path: Path,
) -> list[importlib.metadata.Distribution]:
    matches: list[importlib.metadata.Distribution] = []
    for distribution in importlib.metadata.distributions(path=[str(search_path)]):
        metadata_name = distribution.metadata.get("Name", "")
        if _normalize_distribution_name(metadata_name) == normalized_name:
            matches.append(distribution)
    return matches


def _select_best_distribution(
    distributions: list[importlib.metadata.Distribution],
) -> importlib.metadata.Distribution:
    return max(distributions, key=_distribution_sort_key)


def _distribution_sort_key(
    distribution: importlib.metadata.Distribution,
) -> tuple[int, Version, str, str]:
    version_text = distribution.version
    try:
        version = Version(version_text)
        valid_version = 1
    except InvalidVersion:
        version = Version("0")
        valid_version = 0
    metadata_path = getattr(distribution, "_path", "")
    return (valid_version, version, version_text, str(metadata_path))


def _replace_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _copytree_clean(source: Path, target: Path, ignore_names: set[str] | None = None) -> None:
    if target.exists():
        shutil.rmtree(target)
    ignored = {"__pycache__", "*.pyc", "*.pyo", *(ignore_names or set())}
    shutil.copytree(
        source,
        target,
        symlinks=True,
        ignore=shutil.ignore_patterns(*ignored),
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


def _write_python_runtime_manifest(
    path: Path,
    python_runtime: _PythonRuntimeCopyResult,
    package_policy: str,
    bundled_distributions: list[PythonBundledDistribution],
) -> None:
    data = {
        "version": 1,
        "package_policy": package_policy,
        "python_home": python_runtime.home.name,
        "site_packages": python_runtime.site_packages.relative_to(python_runtime.home).as_posix(),
        "distributions": [
            {
                "name": distribution.name,
                "version": distribution.version,
                "source": distribution.source,
            }
            for distribution in sorted(
                bundled_distributions,
                key=lambda item: (_normalize_distribution_name(item.name), item.source),
            )
        ],
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
