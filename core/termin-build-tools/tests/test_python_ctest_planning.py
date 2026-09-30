from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from termin_build import repository_control
from termin_build.sdk_test_context import load_configured_test_python_bindings


BASE_REGISTRATIONS = {
    "termin_inspect_cpp_test": "termin-inspect",
    "termin_engine_world_controller_test": "termin-engine",
}
PYTHON_REGISTRATIONS = {
    "termin_inspect_python_test": "termin-inspect",
    "termin_engine_python_world_controller_test": "termin-engine",
}
WINDOW_REGISTRATION = "window_probe_test"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def catalog():
    repo = Path(__file__).resolve().parents[3]
    original = repository_control.load_catalog(repo)
    suites = tuple(
        suite for suite in original.suites
        if suite.executor == "ctest" and suite.module in set(BASE_REGISTRATIONS.values())
    )
    assert len(suites) == 2
    return replace(original, suites=suites)


def _configured_graph(build: Path, python_enabled: bool) -> dict[str, object]:
    build.mkdir(parents=True)
    (build / "CMakeCache.txt").write_text(
        "TERMIN_SDK_PROFILE:STRING=full\n"
        f"TERMIN_BUILD_PYTHON:BOOL={'ON' if python_enabled else 'OFF'}\n",
        encoding="utf-8",
    )
    registrations = dict(BASE_REGISTRATIONS)
    if python_enabled:
        registrations.update(PYTHON_REGISTRATIONS)
    registrations[WINDOW_REGISTRATION] = "termin-engine"
    payload = {"tests": []}
    reply = build / ".cmake" / "api" / "v1" / "reply"
    target_refs = []
    for name, module in registrations.items():
        capabilities = ["host"]
        if name in PYTHON_REGISTRATIONS:
            capabilities.append("python-bindings")
        if name == WINDOW_REGISTRATION:
            capabilities.append("window")
        payload["tests"].append({
            "name": name,
            "properties": [{"name": "LABELS", "value": [
                f"termin:module:{module}", "termin:tier:pr",
                f"termin:build-target:{name}",
                *(f"termin:capability:{capability}" for capability in capabilities),
            ]}],
        })
        target_ref = {"jsonFile": f"{name}.json"}
        target_refs.append(target_ref)
        _write_json(reply / target_ref["jsonFile"], {
            "name": name, "type": "EXECUTABLE", "artifacts": [{"path": f"bin/{name}"}],
        })
    # Support modules belong to the dependency graph, rather than the exact
    # set of executable test targets published by an aggregate.
    _write_json(reply / "support.json", {"name": "_cpp_tests", "type": "MODULE_LIBRARY"})
    target_refs.append({"jsonFile": "support.json"})
    _write_json(reply / "index-1.json", {
        "reply": {"codemodel-v2": {"jsonFile": "codemodel.json"}},
    })
    _write_json(reply / "codemodel.json", {
        "configurations": [{"name": "Release", "targets": target_refs}],
    })
    headless_targets = set(BASE_REGISTRATIONS)
    if python_enabled:
        headless_targets.update(PYTHON_REGISTRATIONS)
    aggregates = ["schema=1"]
    for aggregate, targets in (
        ("termin_native_tests", headless_targets),
        ("termin_native_tests_with_window", headless_targets | {WINDOW_REGISTRATION}),
    ):
        aggregates.extend(f"{aggregate}\t{target}" for target in sorted(targets))
    (build / "ctest-build-aggregates.txt").write_text(
        "\n".join(aggregates) + "\n", encoding="utf-8"
    )
    return payload


@pytest.mark.parametrize("python_enabled", [False, True])
@pytest.mark.parametrize("window_enabled", [False, True])
def test_configured_python_tests_participate_in_selection_aggregate_and_report(
    tmp_path: Path, catalog, monkeypatch, python_enabled: bool, window_enabled: bool
) -> None:
    build = tmp_path / "build"
    payload = _configured_graph(build, python_enabled)
    capabilities = ["host"]
    if load_configured_test_python_bindings(build):
        capabilities.append("python-bindings")
    if window_enabled:
        capabilities.append("window")
    selection = repository_control.build_ctest_execution_plan(
        catalog, payload, "pr", "linux", capabilities, "full"
    )
    expected = set(BASE_REGISTRATIONS)
    if python_enabled:
        expected.update(PYTHON_REGISTRATIONS)
    if window_enabled:
        expected.add(WINDOW_REGISTRATION)
    assert {entry["name"] for entry in selection["selected"]} == expected
    assert not any(entry["name"] in PYTHON_REGISTRATIONS for entry in selection["skipped"])
    assert repository_control.validate_ctest_inventory(catalog, payload) == []
    assert repository_control.resolve_ctest_build_targets(
        build, payload, selection, "Release"
    ) == tuple(sorted(expected))
    assert repository_control.resolve_ctest_build_aggregate(
        build, payload, selection, "Release"
    ) == ("termin_native_tests_with_window" if window_enabled else "termin_native_tests")

    selection_path = tmp_path / "selection.json"
    junit = tmp_path / "ctest.xml"
    output = tmp_path / "execution.json"
    _write_json(selection_path, selection)
    junit.write_text(
        "<testsuites><testsuite>"
        + "".join(f'<testcase name="{name}" />' for name in sorted(expected))
        + "</testsuite></testsuites>", encoding="utf-8",
    )
    monkeypatch.setattr(repository_control, "_load_valid_catalog", lambda _root: catalog)
    assert repository_control._cmd_report_ctest(tmp_path, selection_path, junit, output) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["failed"] == []
    assert {suite["id"] for suite in report["executed"]} == {suite.id for suite in catalog.suites}
    assert {entry["name"] for entry in report["details"]["registrations"]["executed"]} == expected
    assert report["sdk_profile"] == "full"


def test_omitting_configured_python_capability_cannot_match_native_aggregate(
    tmp_path: Path, catalog
) -> None:
    build = tmp_path / "build"
    payload = _configured_graph(build, True)
    selection = repository_control.build_ctest_execution_plan(
        catalog, payload, "pr", "linux", ["host"], "full"
    )
    python_skips = {
        entry["name"]: entry["reason"] for entry in selection["skipped"]
        if entry["name"] in PYTHON_REGISTRATIONS
    }
    assert python_skips == {
        name: "missing capabilities: python-bindings" for name in PYTHON_REGISTRATIONS
    }
    with pytest.raises(repository_control.ManifestError, match="exactly matches"):
        repository_control.resolve_ctest_build_aggregate(build, payload, selection, "Release")


@pytest.mark.parametrize("python_enabled", [False, True])
def test_python_native_source_inventory_requires_sources_only_when_configured(
    tmp_path: Path, catalog, python_enabled: bool
) -> None:
    compiled = []
    for suite in catalog.suites:
        source = tmp_path / suite.roots[0] / "test_native.cpp"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("int main() { return 0; }\n", encoding="utf-8")
        compiled.append({"file": str(source)})
    python_sources = (
        "core/termin-inspect/tests/test_python_inspect.cpp",
        "engine/termin-engine/tests/test_python_world_controller.cpp",
    )
    for relative in python_sources:
        (tmp_path / relative).write_text("int main() { return 0; }\n", encoding="utf-8")
    capabilities = ["host", "python-bindings"] if python_enabled else ["host"]
    errors = repository_control.validate_native_compile_inventory(
        tmp_path, catalog, compiled, "pr", capabilities, "full"
    )
    assert len(errors) == (2 if python_enabled else 0)
    if python_enabled:
        assert all(any(relative in error for error in errors) for relative in python_sources)
        compiled.extend({"file": str(tmp_path / relative)} for relative in python_sources)
        assert repository_control.validate_native_compile_inventory(
            tmp_path, catalog, compiled, "pr", capabilities, "full"
        ) == []
