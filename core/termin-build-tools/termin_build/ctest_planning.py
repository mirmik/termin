"""CMake file-api and CTest build planning for repository test suites."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .repository_control_errors import ManifestError


def ctest_labels(raw_test: object) -> tuple[str, ...]:
    """Return the labels published by one CTest JSON registration."""
    if not isinstance(raw_test, dict):
        return ()
    properties = raw_test.get("properties")
    if not isinstance(properties, list):
        return ()
    for property_entry in properties:
        if (
            not isinstance(property_entry, dict)
            or property_entry.get("name") != "LABELS"
        ):
            continue
        value = property_entry.get("value")
        if isinstance(value, list) and all(isinstance(label, str) for label in value):
            return tuple(value)
    return ()


def ctest_discovery_command(build_dir: Path, config: str | None) -> list[str]:
    """Build the CTest JSON-discovery command for a configured tree."""
    command = ["ctest", "--test-dir", str(build_dir)]
    if config:
        command.extend(("-C", config))
    command.append("--show-only=json-v1")
    return command


def load_configured_native_sources(build_dir: Path) -> list[dict[str, str]]:
    """Load native sources from compile commands or the CMake file API."""
    compile_commands_path = build_dir / "compile_commands.json"
    if compile_commands_path.exists():
        try:
            value = json.loads(compile_commands_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ManifestError(
                f"invalid compile commands in {compile_commands_path}: {exc}"
            ) from exc
        if not isinstance(value, list):
            raise ManifestError(
                f"compile commands root must be an array: {compile_commands_path}"
            )
        return value

    reply_dir, codemodel = cmake_file_api_codemodel(build_dir)
    try:
        source_root = Path(codemodel["paths"]["source"])
        sources: set[str] = set()
        for configuration in codemodel["configurations"]:
            for target_ref in configuration.get("targets", []):
                target = json.loads(
                    (reply_dir / target_ref["jsonFile"]).read_text(encoding="utf-8")
                )
                for source_entry in target.get("sources", []):
                    source_path = source_entry.get("path")
                    if not isinstance(source_path, str):
                        continue
                    path = Path(source_path)
                    sources.add(str(path if path.is_absolute() else source_root / path))
    except (KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        raise ManifestError(
            f"invalid CMake file-api codemodel in {reply_dir}: {exc}"
        ) from exc
    return [{"file": source} for source in sorted(sources)]


def cmake_file_api_codemodel(build_dir: Path) -> tuple[Path, dict[str, object]]:
    """Load the latest CMake file-api codemodel reply."""
    reply_dir = build_dir / ".cmake" / "api" / "v1" / "reply"
    indexes = sorted(reply_dir.glob("index-*.json"))
    if not indexes:
        raise ManifestError(
            "CMake file-api codemodel is missing; request codemodel-v2 before "
            f"configuring {build_dir}"
        )
    try:
        index = json.loads(indexes[-1].read_text(encoding="utf-8"))
        codemodel_ref = index["reply"]["codemodel-v2"]
        codemodel = json.loads(
            (reply_dir / codemodel_ref["jsonFile"]).read_text(encoding="utf-8")
        )
    except (KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        raise ManifestError(
            f"invalid CMake file-api codemodel in {reply_dir}: {exc}"
        ) from exc
    if not isinstance(codemodel, dict):
        raise ManifestError(f"invalid CMake file-api codemodel in {reply_dir}")
    return reply_dir, codemodel


def configured_executable_targets(
    build_dir: Path, config: str | None
) -> dict[str, str]:
    """Map configured executable artifact paths to their CMake targets."""
    reply_dir, codemodel = cmake_file_api_codemodel(build_dir)
    configurations = codemodel.get("configurations")
    if not isinstance(configurations, list):
        raise ManifestError(
            f"CMake file-api codemodel has no configurations: {reply_dir}"
        )
    selected_configurations = [
        entry
        for entry in configurations
        if isinstance(entry, dict)
        and (config is None or entry.get("name") == config)
    ]
    if not selected_configurations:
        raise ManifestError(
            f"CMake file-api codemodel has no {config!r} configuration: {reply_dir}"
        )

    targets: dict[str, str] = {}
    try:
        for configuration in selected_configurations:
            for target_ref in configuration.get("targets", []):
                target = json.loads(
                    (reply_dir / target_ref["jsonFile"]).read_text(encoding="utf-8")
                )
                if target.get("type") != "EXECUTABLE":
                    continue
                target_name = target.get("name")
                if not isinstance(target_name, str):
                    continue
                for artifact in target.get("artifacts", []):
                    artifact_path = artifact.get("path")
                    if not isinstance(artifact_path, str):
                        continue
                    absolute_path = Path(artifact_path)
                    if not absolute_path.is_absolute():
                        absolute_path = build_dir / absolute_path
                    targets[os.path.normcase(os.path.abspath(absolute_path))] = (
                        target_name
                    )
    except (KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        raise ManifestError(
            f"invalid CMake executable target in {reply_dir}: {exc}"
        ) from exc
    return targets


def resolve_ctest_build_targets(
    build_dir: Path,
    ctest_payload: object,
    execution_plan: dict[str, object],
    config: str | None,
) -> tuple[str, ...]:
    """Resolve the exact CMake targets required by a selected CTest plan."""
    if not isinstance(ctest_payload, dict) or not isinstance(
        ctest_payload.get("tests"), list
    ):
        raise ManifestError("CTest JSON must contain a tests array")
    selected = execution_plan.get("selected")
    if not isinstance(selected, list):
        raise ManifestError("CTest execution plan has no selected test list")

    registrations = {
        raw_test["name"]: raw_test
        for raw_test in ctest_payload["tests"]
        if isinstance(raw_test, dict) and isinstance(raw_test.get("name"), str)
    }
    executable_targets = configured_executable_targets(build_dir, config)
    configured_target_names = set(executable_targets.values())
    build_targets = set()
    for entry in selected:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise ManifestError("CTest execution plan contains an invalid test")
        name = entry["name"]
        registration = registrations.get(name)
        labels = ctest_labels(registration)
        target_labels = [
            label.removeprefix("termin:build-target:")
            for label in labels
            if label.startswith("termin:build-target:")
        ]
        if len(target_labels) > 1:
            raise ManifestError(
                f"CTest test {name} has multiple termin:build-target labels"
            )
        if target_labels:
            target = target_labels[0]
            if target not in configured_target_names:
                raise ManifestError(
                    f"CTest test {name} names unknown CMake build target: {target}"
                )
            build_targets.add(target)
            continue

        command = registration.get("command") if registration else None
        if (
            not isinstance(command, list)
            or not command
            or not isinstance(command[0], str)
        ):
            raise ManifestError(
                f"CTest test {name} has no termin:build-target label or "
                "executable command"
            )
        command_path = os.path.normcase(os.path.abspath(command[0]))
        target = executable_targets.get(command_path)
        if target is None:
            raise ManifestError(
                f"CTest test {name} executable is not a configured CMake target: "
                f"{command[0]}"
            )
        build_targets.add(target)
    return tuple(sorted(build_targets))


def configured_ctest_build_aggregates(
    build_dir: Path,
) -> dict[str, frozenset[str]]:
    """Load configured aggregate targets and their exact test-target sets."""
    manifest = build_dir / "ctest-build-aggregates.txt"
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ManifestError(
            f"cannot read configured CTest aggregate manifest {manifest}: {exc}"
        ) from exc
    if not lines or lines[0] != "schema=1":
        raise ManifestError(f"invalid CTest aggregate manifest header in {manifest}")

    aggregates: dict[str, set[str]] = {}
    for line_number, line in enumerate(lines[1:], start=2):
        fields = line.split("\t")
        if len(fields) != 2 or not all(fields):
            raise ManifestError(
                f"invalid CTest aggregate manifest entry at {manifest}:{line_number}"
            )
        aggregate, target = fields
        aggregates.setdefault(aggregate, set()).add(target)
    if not aggregates:
        raise ManifestError(f"CTest aggregate manifest is empty: {manifest}")
    return {
        aggregate: frozenset(targets) for aggregate, targets in aggregates.items()
    }


def resolve_ctest_build_aggregate(
    build_dir: Path,
    ctest_payload: object,
    execution_plan: dict[str, object],
    config: str | None,
) -> str:
    """Resolve the one aggregate whose target set exactly matches the plan."""
    selected_targets = frozenset(
        resolve_ctest_build_targets(build_dir, ctest_payload, execution_plan, config)
    )
    aggregates = configured_ctest_build_aggregates(build_dir)
    matches = sorted(
        aggregate
        for aggregate, targets in aggregates.items()
        if targets == selected_targets
    )
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ManifestError(
            "multiple CTest build aggregates match the selected plan: "
            + ", ".join(matches)
        )

    diagnostics = []
    for aggregate, targets in sorted(aggregates.items()):
        missing = sorted(selected_targets - targets)
        unexpected = sorted(targets - selected_targets)
        diagnostics.append(
            f"{aggregate}: missing={missing[:5]!r}, unexpected={unexpected[:5]!r}"
        )
    raise ManifestError(
        "no configured CTest build aggregate exactly matches the selected plan; "
        + "; ".join(diagnostics)
    )
