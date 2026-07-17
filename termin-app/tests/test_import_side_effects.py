from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_TOOL = REPO_ROOT / "tools" / "import_side_effects_audit.py"


def _subprocess_env() -> dict[str, str]:
    return {
        **os.environ,
        "TERMIN_SDK": str(REPO_ROOT / "sdk"),
    }


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
    "termin.editor_core.resource_manager",
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
        env=_subprocess_env(),
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


def test_native_component_extension_projection_keeps_domain_extensions_lazy() -> None:
    script = """
import sys

import termin.editor_native.component_extensions

assert "termin.foliage" not in sys.modules
assert "termin.editor_core.foliage_layer_editor_extension" not in sys.modules
assert "termin.editor_core.procedural_mesh_editor_extension" not in sys.modules
assert "termin.csg.operation_specs" not in sys.modules
assert "termin.editor_native.foliage_extension" not in sys.modules
assert "termin.editor_native.procedural_mesh_extension" not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=_subprocess_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    assert "nanobind: leaked" not in result.stderr


def test_removed_app_asset_resource_paths_do_not_resolve() -> None:
    script = """
import importlib

old_assets = "termin" + ".assets"
old_resources = old_assets + ".resources"
removed_paths = [
    old_assets,
    old_assets + ".project_file_watcher",
    old_resources,
    old_resources + "._manager",
    old_resources + "._components",
    old_resources + "._builtins",
]

for path in removed_paths:
    try:
        importlib.import_module(path)
    except ModuleNotFoundError:
        continue
    raise AssertionError(f"removed app asset path still imports: {path}")

print("removed")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=_subprocess_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "removed\n"
    assert "nanobind: leaked" not in result.stderr


def test_module_context_import_does_not_load_old_app_asset_namespace() -> None:
    script = """
import sys
import termin_modules.module_context

old_assets = "termin" + ".assets"
assert old_assets not in sys.modules
print("clean")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=_subprocess_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "clean\n"
    assert "nanobind: leaked" not in result.stderr


def test_project_modules_runtime_does_not_leave_nanobind_callback_refcycle() -> None:
    script = """
from termin.project_modules.runtime import ProjectModulesRuntime

runtime = ProjectModulesRuntime()
runtime.close()
print("closed")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=_subprocess_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "closed\n"
    assert "nanobind: leaked" not in result.stderr


def test_module_runtime_clear_callbacks_releases_python_callable_refcycle() -> None:
    script = """
from termin_modules import ModuleRuntime

runtime = ModuleRuntime()
runtime.set_event_callback(lambda event: None)
runtime.set_build_output_callback(lambda module_id, line: None)
runtime.clear_callbacks()
print("cleared")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=_subprocess_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "cleared\n"
    assert "nanobind: leaked" not in result.stderr


def test_voxelize_source_import_is_enum_only_and_clean() -> None:
    script = """
import sys

from termin.voxels import VoxelizeSource

print(VoxelizeSource.CURRENT_MESH.name)
assert "termin_voxel_components.voxelizer_component" not in sys.modules
assert "termin.render" not in sys.modules
assert "termin.materials" not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=_subprocess_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "CURRENT_MESH\n"
    assert "nanobind: leaked" not in result.stderr


def test_python_component_import_registries_cleanup_before_nanobind_shutdown() -> None:
    script = """
from termin.navmesh.builder_component import NavMeshBuilderComponent

print(NavMeshBuilderComponent.__name__)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=_subprocess_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "NavMeshBuilderComponent\n"
    assert "nanobind: leaked" not in result.stderr


def test_default_pipeline_python_pass_factory_releases_owned_pass() -> None:
    script = """
from termin.bootstrap import bootstrap_player
from termin.engine import EngineCore, register_default_scene_extensions
from termin.render_framework import tc_pipeline_destroy, tc_pipeline_registry_get_all_info

bootstrap_player()
register_default_scene_extensions()
engine = EngineCore()
pipeline = engine.rendering_manager.create_pipeline("Default")
print(pipeline.pass_count)
for info in list(tc_pipeline_registry_get_all_info()):
    tc_pipeline_destroy(info["handle"])
del pipeline
del engine
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=_subprocess_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "8\n"
    assert "nanobind: leaked" not in result.stderr


def test_rendering_manager_stats_expose_pipeline_cache_counters() -> None:
    script = """
import json
from termin.bootstrap import bootstrap_player
from termin.engine import EngineCore

bootstrap_player()
engine = EngineCore()
stats = engine.rendering_manager.get_render_stats()
print(json.dumps({
    "pipeline_cache_hits": stats["pipeline_cache_hits"],
    "pipeline_cache_misses": stats["pipeline_cache_misses"],
    "pipeline_cache_create_pipeline_count": stats["pipeline_cache_create_pipeline_count"],
    "pipeline_cache_cached_pipelines": stats["pipeline_cache_cached_pipelines"],
    "pipeline_cache_unique_vertex_layout_signatures": stats["pipeline_cache_unique_vertex_layout_signatures"],
    "pipeline_cache_vertex_layout_signature_hashes": stats["pipeline_cache_vertex_layout_signature_hashes"],
}, sort_keys=True))
del engine
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=_subprocess_env(),
        check=True,
        capture_output=True,
        text=True,
    )

    stats = json.loads(result.stdout)
    assert stats == {
        "pipeline_cache_cached_pipelines": 0,
        "pipeline_cache_create_pipeline_count": 0,
        "pipeline_cache_hits": 0,
        "pipeline_cache_misses": 0,
        "pipeline_cache_unique_vertex_layout_signatures": 0,
        "pipeline_cache_vertex_layout_signature_hashes": [],
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
    "termin.animation_components",
    "termin.audio",
    "termin.audio.components",
    "termin.colliders",
    "termin.kinematic",
    "termin.mesh",
    "termin.navmesh",
    "termin.physics_components",
    "termin.render_components",
    "termin.render_passes",
    "termin.render_framework",
    "termin.skeleton_components",
    "termin.tween",
    "termin.ui_components",
    "termin.voxels",
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
