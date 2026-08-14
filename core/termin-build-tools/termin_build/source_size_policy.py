"""Manifest-driven repository source-size policy."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


POLICY_MANIFEST = Path("build-system/repository-policies.json")


class SourceSizePolicyError(ValueError):
    """Raised when source-size policy metadata is invalid."""


@dataclass(frozen=True)
class SourceSizeBaseline:
    path: str
    max_lines: int
    reason: str


@dataclass(frozen=True)
class SourceSizePolicy:
    threshold: int
    extensions: tuple[str, ...]
    exclude_roots: tuple[str, ...]
    baselines: tuple[SourceSizeBaseline, ...] = ()

    def line_limit(self, path: str) -> int:
        for baseline in self.baselines:
            if baseline.path == path:
                return baseline.max_lines
        return self.threshold - 1


def _string_tuple(raw: object, context: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or not raw:
        raise SourceSizePolicyError(f"{context} must be a non-empty list")
    if any(not isinstance(item, str) or not item for item in raw):
        raise SourceSizePolicyError(f"{context} must contain non-empty strings")
    if len(raw) != len(set(raw)):
        raise SourceSizePolicyError(f"{context} contains duplicate values")
    return tuple(raw)


def load_source_size_policy(repo_root: Path) -> SourceSizePolicy:
    path = repo_root / POLICY_MANIFEST
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SourceSizePolicyError(f"policy manifest does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SourceSizePolicyError(f"invalid policy manifest {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise SourceSizePolicyError(f"unsupported or missing schema in {path}")
    raw = data.get("source_size")
    if not isinstance(raw, dict):
        raise SourceSizePolicyError(f"{path}: source_size must be an object")
    threshold = raw.get("threshold")
    if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold <= 0:
        raise SourceSizePolicyError(f"{path}: source_size.threshold must be positive")
    extensions = _string_tuple(raw.get("extensions"), f"{path}: extensions")
    if any(not extension.startswith(".") for extension in extensions):
        raise SourceSizePolicyError(f"{path}: extensions must start with '.'")
    exclude_roots = _string_tuple(raw.get("exclude_roots"), f"{path}: exclude_roots")
    for root in exclude_roots:
        candidate = Path(root)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise SourceSizePolicyError(
                f"{path}: exclude root must be repository-relative: {root}"
            )
    raw_baselines = raw.get("baselines", [])
    if not isinstance(raw_baselines, list):
        raise SourceSizePolicyError(f"{path}: baselines must be a list")
    baselines = []
    baseline_paths = set()
    for index, entry in enumerate(raw_baselines):
        context = f"{path}: baselines[{index}]"
        if not isinstance(entry, dict):
            raise SourceSizePolicyError(f"{context} must be an object")
        baseline_path = entry.get("path")
        max_lines = entry.get("max_lines")
        reason = entry.get("reason")
        if not isinstance(baseline_path, str) or not baseline_path:
            raise SourceSizePolicyError(f"{context}.path must be a non-empty string")
        candidate = Path(baseline_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise SourceSizePolicyError(
                f"{context}.path must be repository-relative: {baseline_path}"
            )
        normalized_path = candidate.as_posix()
        if normalized_path in baseline_paths:
            raise SourceSizePolicyError(
                f"{path}: duplicate source-size baseline: {normalized_path}"
            )
        if candidate.suffix.lower() not in extensions:
            raise SourceSizePolicyError(
                f"{context}.path extension is not covered by source-size policy"
            )
        if (
            not isinstance(max_lines, int)
            or isinstance(max_lines, bool)
            or max_lines < threshold
        ):
            raise SourceSizePolicyError(
                f"{context}.max_lines must be an integer >= {threshold}"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise SourceSizePolicyError(f"{context}.reason must be a non-empty string")
        baseline_file = repo_root / candidate
        if not baseline_file.is_file():
            raise SourceSizePolicyError(
                f"{context}.path does not exist: {normalized_path}"
            )
        with baseline_file.open("rb") as stream:
            current_lines = sum(1 for _ in stream)
        if current_lines < threshold:
            raise SourceSizePolicyError(
                f"{context} is stale: {normalized_path} has {current_lines} lines"
            )
        baseline_paths.add(normalized_path)
        baselines.append(SourceSizeBaseline(normalized_path, max_lines, reason.strip()))
    return SourceSizePolicy(threshold, extensions, exclude_roots, tuple(baselines))


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _is_excluded(path: Path, root: Path) -> bool:
    if len(root.parts) == 1:
        return root.name in path.parts
    return _is_within(path, root)


def find_long_files(
    repo_root: Path, policy: SourceSizePolicy
) -> tuple[tuple[str, int], ...]:
    excluded = tuple(Path(root) for root in policy.exclude_roots)
    extensions = {extension.lower() for extension in policy.extensions}
    results = []
    for current, directory_names, file_names in os.walk(repo_root):
        relative_current = Path(current).relative_to(repo_root)
        directory_names[:] = [
            name
            for name in directory_names
            if not any(_is_excluded(relative_current / name, root) for root in excluded)
        ]
        if any(_is_excluded(relative_current, root) for root in excluded):
            continue
        for name in file_names:
            path = Path(current) / name
            if path.suffix.lower() not in extensions:
                continue
            try:
                with path.open("rb") as stream:
                    line_count = sum(1 for _ in stream)
            except (PermissionError, IsADirectoryError):
                continue
            relative_path = path.relative_to(repo_root).as_posix()
            if line_count > policy.line_limit(relative_path):
                results.append((relative_path, line_count))
    return tuple(sorted(results, key=lambda entry: (-entry[1], entry[0])))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--threshold", "-t", type=int)
    parser.add_argument("--exclude", "-e", action="append")
    parser.add_argument("--extension", "-x", action="append")
    parser.add_argument("--fail", action="store_true")
    args = parser.parse_args(argv)
    repo_root = args.root.resolve()
    try:
        policy = load_source_size_policy(repo_root)
        if args.threshold is not None:
            if args.threshold <= 0:
                raise SourceSizePolicyError("threshold override must be positive")
            policy = SourceSizePolicy(
                args.threshold,
                policy.extensions,
                policy.exclude_roots,
                policy.baselines,
            )
        if args.exclude:
            policy = SourceSizePolicy(
                policy.threshold,
                policy.extensions,
                (*policy.exclude_roots, *args.exclude),
                policy.baselines,
            )
        if args.extension:
            extensions = tuple(
                value if value.startswith(".") else f".{value}"
                for value in args.extension
            )
            policy = SourceSizePolicy(
                policy.threshold,
                extensions,
                policy.exclude_roots,
                policy.baselines,
            )
        results = find_long_files(repo_root, policy)
    except SourceSizePolicyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not results:
        print(f"No source files with >= {policy.threshold} lines found.")
        return 0
    print(f"Source files with >= {policy.threshold} lines:\n")
    for path, lines in results:
        print(f"  {lines:>6}  {path}")
    print(f"\nTotal: {len(results)} file(s)")
    return 1 if args.fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
