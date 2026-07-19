from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class WarmupResult:
    project_root: Path
    requested_modules: tuple[str, ...]
    success: bool
    failed_modules: tuple[str, ...]


def warmup_project_modules(
    project_root: str | Path,
    *,
    module_ids: Sequence[str] = (),
    build_module_ids: Sequence[str] = (),
    clean_module_ids: Sequence[str] = (),
    rebuild_module_ids: Sequence[str] = (),
    runtime: Any | None = None,
) -> WarmupResult:
    resolved_project_root = resolve_project_root(Path(project_root))
    modules_runtime = runtime if runtime is not None else _project_modules_runtime()
    previous_sync_live_scenes = None
    if runtime is None:
        previous_sync_live_scenes = modules_runtime.sync_live_scenes
        modules_runtime.set_sync_live_scenes(False)
    operations = (
        *((module_id, "warm up", modules_runtime.load_module) for module_id in module_ids),
        *((module_id, "build", modules_runtime.build_module) for module_id in build_module_ids),
        *((module_id, "clean", modules_runtime.clean_module) for module_id in clean_module_ids),
        *((module_id, "rebuild", modules_runtime.rebuild_module) for module_id in rebuild_module_ids),
    )
    requested = tuple(module_id for module_id, _, _ in operations)

    try:
        if operations:
            if not modules_runtime.discover_project(resolved_project_root):
                _log_error(
                    "[ProjectModulesWarmup] failed to discover project modules for "
                    f"{resolved_project_root}: {modules_runtime.last_error}"
                )
                return WarmupResult(resolved_project_root, requested, False, ())

            success = True
            for module_id, operation_name, operation in operations:
                if modules_runtime.find(module_id) is None:
                    _log_error(f"[ProjectModulesWarmup] unknown project module: {module_id}")
                    success = False
                    continue
                if not operation(module_id):
                    _log_error(
                        f"[ProjectModulesWarmup] failed to {operation_name} module '{module_id}': "
                        f"{modules_runtime.last_error}"
                    )
                    success = False
        else:
            success = modules_runtime.load_project(resolved_project_root)
            if not success:
                _log_error(
                    "[ProjectModulesWarmup] failed to warm up project modules for "
                    f"{resolved_project_root}: {modules_runtime.last_error}"
                )

        failed_modules = tuple(
            record.id
            for record in modules_runtime.records()
            if record.state.name == "Failed"
        )
        if failed_modules:
            success = False

        return WarmupResult(resolved_project_root, requested, success, failed_modules)
    finally:
        if previous_sync_live_scenes is not None:
            modules_runtime.set_sync_live_scenes(previous_sync_live_scenes)


def resolve_project_root(requested: Path) -> Path:
    start = requested if str(requested) else Path.cwd()
    if not start.is_absolute():
        start = Path.cwd() / start
    try:
        start = start.resolve()
    except OSError:
        start = start.absolute()

    if start.is_file():
        if start.suffix != ".terminproj":
            raise RuntimeError(f"project path is a file, but not a .terminproj: {start}")
        return start.parent

    if not start.exists():
        raise RuntimeError(f"project path does not exist: {start}")
    if not start.is_dir():
        raise RuntimeError(f"project path is not a directory: {start}")

    for directory in (start, *start.parents):
        if _contains_termin_project_file(directory):
            return directory

    raise RuntimeError(f"could not find a .terminproj file from: {start}")


def _contains_termin_project_file(directory: Path) -> bool:
    try:
        return any(path.is_file() for path in directory.glob("*.terminproj"))
    except OSError as exc:
        _log_error(f"[ProjectModulesWarmup] failed to inspect project directory {directory}: {exc}")
        return False


def _log_error(message: str) -> None:
    try:
        from tcbase import log
    except Exception:
        print(message, file=sys.stderr)
        return
    log.error(message)


def _project_modules_runtime() -> Any:
    from termin.project_modules.runtime import get_project_modules_runtime

    return get_project_modules_runtime()


def _bootstrap_runtime() -> None:
    """Initialize the native type hierarchy used while validating modules."""
    from termin.bootstrap import bootstrap_runtime

    bootstrap_runtime()


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="termin modules",
        description="Warm up Termin project modules from the command line.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="warmup",
        choices=("warmup",),
        help="Command to run. Defaults to warmup.",
    )
    parser.add_argument(
        "project",
        nargs="?",
        type=Path,
        default=None,
        help="Project directory or .terminproj file. Defaults to the current directory.",
    )
    parser.add_argument(
        "--project",
        "-p",
        dest="project_option",
        type=Path,
        default=None,
        help="Project directory or .terminproj file.",
    )
    parser.add_argument(
        "--module",
        "-m",
        dest="module_ids",
        action="append",
        default=[],
        help="Warm up only the specified module id. Repeat for multiple modules.",
    )
    parser.add_argument(
        "--build-module",
        dest="build_module_ids",
        action="append",
        default=[],
        help="Build the specified module without loading it. Repeatable.",
    )
    parser.add_argument(
        "--clean-module",
        dest="clean_module_ids",
        action="append",
        default=[],
        help="Clean artifacts for the specified module. Repeatable.",
    )
    parser.add_argument(
        "--rebuild-module",
        dest="rebuild_module_ids",
        action="append",
        default=[],
        help="Clean and rebuild the specified module without loading it. Repeatable.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print errors.",
    )
    return parser


def _normalize_argv(argv: Sequence[str]) -> list[str]:
    if not argv:
        return ["warmup"]
    first = argv[0]
    if first == "help":
        return ["--help", *argv[1:]]
    if first in {"warmup", "-h", "--help"}:
        return list(argv)
    return ["warmup", *argv]


def _print_summary(result: WarmupResult, runtime: Any) -> None:
    records = runtime.records()
    print(f"Project: {result.project_root}")
    if result.requested_modules:
        print(f"Requested modules: {', '.join(result.requested_modules)}")
    print(f"Modules: {len(records)}")
    for record in records:
        descriptor = Path(record.descriptor_path)
        print(f"  {record.id}: {record.kind.name} {record.state.name} ({descriptor})")
        if record.error_message:
            print(f"    error: {record.error_message}", file=sys.stderr)
        if record.diagnostics:
            print(f"    diagnostics: {record.diagnostics}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _create_parser()
    args = parser.parse_args(_normalize_argv(sys.argv[1:] if argv is None else argv))
    project_path = args.project_option if args.project_option is not None else args.project
    if project_path is None:
        project_path = Path.cwd()

    try:
        _bootstrap_runtime()
        result = warmup_project_modules(
            project_path,
            module_ids=tuple(args.module_ids),
            build_module_ids=tuple(args.build_module_ids),
            clean_module_ids=tuple(args.clean_module_ids),
            rebuild_module_ids=tuple(args.rebuild_module_ids),
        )
        runtime = _project_modules_runtime()
    except Exception as exc:
        _log_error(f"[ProjectModulesWarmup] {exc}")
        print(f"termin modules: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        _print_summary(result, runtime)

    if not result.success:
        if result.failed_modules:
            print(
                "termin modules: failed modules: "
                + ", ".join(result.failed_modules),
                file=sys.stderr,
            )
        elif runtime.last_error:
            print(f"termin modules: {runtime.last_error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
