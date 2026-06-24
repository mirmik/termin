from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_TOOL = REPO_ROOT / "tools" / "import_side_effects_audit.py"


def _load_audit_tool():
    spec = importlib.util.spec_from_file_location("import_side_effects_audit", AUDIT_TOOL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_import_side_effect_audit_reports_top_level_runtime_resources(tmp_path: Path) -> None:
    audit_tool = _load_audit_tool()
    module_path = tmp_path / "sample_module.py"
    module_path.write_text(
        "\n".join(
            [
                "import logging",
                "from dataclasses import field",
                "from tcbase.profiler import Profiler",
                "",
                "logger = logging.getLogger(__name__)",
                "safe = field(default_factory=dict)",
                "profiler = Profiler.instance()",
                "# termin-import-ok: synthetic legacy singleton accepted for this file",
                "legacy = DefaultResourceManager.instance()",
                "",
            ]
        ),
        encoding="utf-8",
    )

    findings = audit_tool.audit_file(module_path, root=tmp_path)

    assert [(finding.category, finding.target) for finding in findings] == [
        ("runtime-singleton-or-io", "profiler = Profiler.instance")
    ]


def test_import_side_effect_audit_can_report_mutable_module_state(tmp_path: Path) -> None:
    audit_tool = _load_audit_tool()
    module_path = tmp_path / "sample_state.py"
    module_path.write_text(
        "\n".join(
            [
                "from collections import defaultdict",
                "",
                "registry = {}",
                "pending_items = []",
                "resource_factories = defaultdict(list)",
                "builtin_components = collect_builtin_components()",
                "# termin-import-ok: constant lookup populated intentionally",
                "known_values = set()",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert audit_tool.audit_file(module_path, root=tmp_path) == []

    findings = audit_tool.audit_file(
        module_path,
        root=tmp_path,
        include_mutable_state=True,
    )

    assert [(finding.category, finding.confidence, finding.target) for finding in findings] == [
        ("module-mutable-state", "low", "registry = dict"),
        ("module-mutable-state", "low", "pending_items = list"),
        ("module-mutable-state", "low", "resource_factories = defaultdict"),
        (
            "module-state-initializer-call",
            "low",
            "builtin_components = collect_builtin_components",
        ),
    ]


def test_importing_runtime_surfaces_does_not_create_runtime_singletons() -> None:
    script = """
import importlib
import json

modules = [
    "tcgui.widgets.renderer",
    "tcgui.widgets.ui",
    "termin.assets.resources",
    "termin.default_assets.resource_manager",
    "termin.project_build.desktop_build",
    "termin.project_build.profile_build",
    "termin.render_framework",
]
for module in modules:
    importlib.import_module(module)

from termin.default_assets.builtin_types import (
    get_default_builtin_component_specs,
    get_default_builtin_frame_pass_specs,
)
from tcbase.profiler import Profiler
from termin_assets import get_resource_manager
from termin.default_assets.resource_manager import DefaultResourceManager
from termin.render_framework import tc_pass_registry_get_all_instance_info

component_specs = get_default_builtin_component_specs()
frame_pass_specs = get_default_builtin_frame_pass_specs()

print(json.dumps({
    "component_specs": len(component_specs),
    "frame_pass_specs": len(frame_pass_specs),
    "profiler_instance": Profiler._instance is not None,
    "resource_manager_factory_active": get_resource_manager() is not None,
    "resource_manager_instance": DefaultResourceManager._instance is not None,
    "pass_instances": tc_pass_registry_get_all_instance_info(),
}, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    state = json.loads(result.stdout)
    assert state == {
        "component_specs": 35,
        "frame_pass_specs": 23,
        "profiler_instance": False,
        "resource_manager_factory_active": False,
        "resource_manager_instance": False,
        "pass_instances": [],
    }
    assert "nanobind: leaked" not in result.stderr


def test_collecting_builtin_specs_does_not_import_runtime_packages() -> None:
    script = """
import json
import sys

from termin.default_assets.builtin_types import (
    get_default_builtin_component_specs,
    get_default_builtin_frame_pass_specs,
)

component_specs = get_default_builtin_component_specs()
frame_pass_specs = get_default_builtin_frame_pass_specs()
runtime_packages = [
    "termin.render_components",
    "termin.render_passes",
    "termin.render_framework",
    "termin.ui_components",
]

print(json.dumps({
    "component_specs": len(component_specs),
    "frame_pass_specs": len(frame_pass_specs),
    "loaded_runtime_packages": [
        module for module in runtime_packages if module in sys.modules
    ],
}, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    state = json.loads(result.stdout)
    assert state == {
        "component_specs": 35,
        "frame_pass_specs": 23,
        "loaded_runtime_packages": [],
    }
    assert "nanobind: leaked" not in result.stderr


def test_spacemouse_controller_loads_libspnav_lazily() -> None:
    script = """
import ctypes.util
import json

calls = []

def fake_find_library(name):
    calls.append(name)
    return None

ctypes.util.find_library = fake_find_library

import termin.editor_core.spacemouse_controller as spacemouse_controller

calls_after_import = list(calls)
controller = spacemouse_controller.SpaceMouseController()
opened = controller.open(None, lambda: None)

print(json.dumps({
    "calls_after_import": calls_after_import,
    "calls_after_open": calls,
    "opened": opened,
}, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    state = json.loads(result.stdout)
    assert state == {
        "calls_after_import": [],
        "calls_after_open": ["spnav"],
        "opened": False,
    }
    assert "nanobind: leaked" not in result.stderr
