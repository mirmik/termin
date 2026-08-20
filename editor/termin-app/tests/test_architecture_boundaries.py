import ast
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DISTRICT_NAMES = ("core", "graphics", "engine", "editor", "physics", "platform")
PACKAGE_DISTRICT = {
    "termin-animation": "graphics",
    "termin-app": "editor",
    "termin-base": "core",
    "termin-collision": "physics",
    "termin-components": "engine",
    "termin-default-assets": "engine",
    "termin-engine": "engine",
    "termin-glb": "graphics",
    "termin-inspect": "core",
    "termin-materials": "graphics",
    "termin-navmesh": "physics",
    "termin-project": "editor",
    "termin-project-build": "editor",
    "termin-render": "engine",
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _package_roots() -> list[Path]:
    return [
        path
        for district_name in DISTRICT_NAMES
        for path in (REPO_ROOT / district_name).iterdir()
        if path.is_dir() and path.name.startswith("termin-")
    ]


def _owned_path(package_relative_path: str) -> Path:
    package_name = package_relative_path.split("/", 1)[0]
    return REPO_ROOT / PACKAGE_DISTRICT[package_name] / package_relative_path


def test_android_runtime_uses_rendering_manager_topology() -> None:
    bootstrap = _read_text(REPO_ROOT / "platform/termin-android/src/bootstrap.cpp")
    activity = _read_text(
        REPO_ROOT
        / "platform/termin-android/platform/app/src/main/java/org/termin/android/TerminActivity.java"
    )
    scene = json.loads(_read_text(REPO_ROOT / "platform/termin-android/assets/scene.json"))

    required_bootstrap_fragments = (
        "create_offscreen_display(",
        "attach_scene_full(",
        "tick_and_render(",
        "validate_output(",
        "compose_and_present(",
    )
    forbidden_bootstrap_fragments = (
        "RenderTargetContext",
        "find_player_camera",
        "player_pipeline",
        "player_color_target",
        "player_depth_target",
        "std::vector<termin::Light>",
        "render_scene_pipeline_offscreen(",
        "#if 0",
    )

    assert [
        fragment
        for fragment in required_bootstrap_fragments
        if fragment not in bootstrap
    ] == []
    assert [
        fragment
        for fragment in forbidden_bootstrap_fragments
        if fragment in bootstrap
    ] == []
    assert "nativeRenderFrame(frameTimeNanos)" in activity

    mount = scene["extensions"]["render_mount"]
    assert mount["viewport_configs"][0]["display_name"] == "Main"
    assert mount["viewport_configs"][0]["render_target"]["name"] == "Main Target"
    target = mount["render_target_configs"][0]
    assert target["camera_uuid"] == "android-camera-entity"
    assert target["pipeline_name"] == "Default"
    assert target["dynamic_resolution"] is True


def test_editor_camera_mode_controller_has_no_frontend_dependency() -> None:
    sources = (
        REPO_ROOT / "editor/termin-app/termin/editor_core/editor_camera.py",
        REPO_ROOT / "editor/termin-app/termin/editor_core/editor_camera_ui_controller.py",
    )
    forbidden_modules = ("tcgui", "termin.gui_native")
    forbidden_names = ("UIComponent", "EditorInteractionSystem")
    offenders: list[str] = []

    for source in sources:
        text = _read_text(source)
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported = (node.module or "",)
            else:
                continue
            for module in imported:
                if module.startswith(forbidden_modules):
                    offenders.append(f"{source.name}: {module}")
        for name in forbidden_names:
            if name in text:
                offenders.append(f"{source.name}: {name}")

    assert offenders == []


def test_engine_runtime_session_has_no_editor_host_participants() -> None:
    source = _read_text(REPO_ROOT / "engine/termin-engine/src/engine_core.cpp")
    start = source.index("class RuntimeSession")
    end = source.index("\n        };\n\n    } // namespace engine_detail", start)
    runtime_session = source[start:end]

    forbidden = (
        "Editor",
        "Binding",
        "Callback",
        "Provider",
        "std::function",
        "PyObject",
        "nb::",
    )
    assert [name for name in forbidden if name in runtime_session] == []
    assert not (
        REPO_ROOT
        / "editor/termin-app/termin/editor_core/primary_render_scene_binding.py"
    ).exists()


def test_runtime_types_have_no_incremental_publication_api() -> None:
    forbidden = (
        "tc_runtime_type_registry_ensure_type",
        "tc_runtime_type_registry_set_owner",
        "tc_runtime_type_registry_set_parent",
        "tc_runtime_type_registry_set_facet",
        "tc_runtime_type_registry_remove_facet",
        "tc_component_registry_register(",
        "tc_component_registry_register_with_parent",
        "tc_component_registry_register_abstract",
        "tc_pass_registry_register(",
        "TC_MODULE_INSPECT_",
        "ComponentRegistrar<",
        "register_python_fields\"",
    )
    source_roots = _package_roots()
    suffixes = {".h", ".hpp", ".c", ".cc", ".cpp", ".cxx", ".py", ".cs"}
    offenders: list[str] = []
    for root in source_roots:
        for path in root.rglob("*"):
            relative_parts = path.relative_to(root).parts
            if path.suffix not in suffixes or any(
                part in {"tests", "docs", "build", "sdk"} for part in relative_parts
            ):
                continue
            text = _read_text(path)
            for symbol in forbidden:
                if symbol in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {symbol}")

    assert offenders == []


def test_scene_owns_component_ref_and_entity_binding_helpers() -> None:
    scene_component_ref_binding = (
        REPO_ROOT / "engine/termin-scene/include/termin/bindings/tc_component_ref_bindings.hpp"
    )
    scene_entity_helpers = REPO_ROOT / "engine/termin-scene/include/termin/bindings/entity_helpers.hpp"
    app_duplicate_paths = [
        REPO_ROOT / "editor/termin-app/cpp/termin/entity/tc_component_ref.hpp",
        REPO_ROOT / "editor/termin-app/cpp/termin/bindings/entity/entity_helpers.hpp",
    ]

    assert scene_component_ref_binding.is_file()
    assert scene_entity_helpers.is_file()
    assert [path for path in app_duplicate_paths if path.exists()] == []


def test_no_app_private_entity_helper_includes_remain() -> None:
    forbidden_includes = (
        '#include "termin/entity/tc_component_ref.hpp"',
        "#include <termin/entity/tc_component_ref.hpp>",
        '#include "termin/bindings/entity/entity_helpers.hpp"',
        "#include <termin/bindings/entity/entity_helpers.hpp>",
    )
    source_roots = [
        REPO_ROOT / "editor/termin-app/cpp",
        REPO_ROOT / "engine/termin-scene",
        *sorted(REPO_ROOT.glob("engine/termin-components/*")),
    ]

    offenders: list[str] = []
    for root in source_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix not in {".h", ".hpp", ".cpp", ".cc", ".cxx"}:
                continue
            text = _read_text(path)
            for include in forbidden_includes:
                if include in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {include}")

    assert offenders == []


def test_platform_cmake_does_not_include_app_private_sources() -> None:
    forbidden_fragments = (
        "../termin-app",
        "termin-app/core_c",
        "termin-app/cpp/termin/render/tc_opengl.cpp",
    )
    cmake_paths = [
        path
        for root in _package_roots()
        for path in root.rglob("*")
        if path.name == "CMakeLists.txt" or path.suffix == ".cmake"
    ]
    cmake_paths = [
        path
        for path in cmake_paths
        if "termin-app" not in path.relative_to(REPO_ROOT).parts
    ]

    offenders: list[str] = []
    for path in cmake_paths:
        text = _read_text(path)
        for fragment in forbidden_fragments:
            if fragment in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {fragment}")

    assert offenders == []


def test_voxels_own_voxel_grid_native_headers() -> None:
    canonical_header = REPO_ROOT / "engine/termin-voxels/termin/voxels/voxel_grid_handle.hpp"
    app_compat_header = REPO_ROOT / "editor/termin-app/cpp/termin/assets/voxel_grid_handle.hpp"
    forbidden_includes = (
        '#include "termin/assets/voxel_grid_handle.hpp"',
        "#include <termin/assets/voxel_grid_handle.hpp>",
    )
    source_roots = [
        REPO_ROOT / "editor/termin-app/cpp",
        REPO_ROOT / "engine/termin-voxels",
        *sorted(REPO_ROOT.glob("engine/termin-components/*")),
        REPO_ROOT / "engine/termin-bootstrap",
    ]

    assert canonical_header.is_file()
    assert not app_compat_header.exists()

    offenders: list[str] = []
    for root in source_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix not in {".h", ".hpp", ".cpp", ".cc", ".cxx"}:
                continue
            text = _read_text(path)
            for include in forbidden_includes:
                if include in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {include}")

    assert offenders == []


def test_app_cxx_tree_contains_only_editor_private_native_sources() -> None:
    app_cpp_root = REPO_ROOT / "editor/termin-app/cpp/termin"
    canonical_paths = [
        REPO_ROOT / "core/termin-base/python/bindings/geom/geom_module.cpp",
        REPO_ROOT / "engine/termin-scene/include/termin/entity/cmp_ref.hpp",
        REPO_ROOT / "engine/termin-scene/include/termin/bindings/entity_bindings.hpp",
        REPO_ROOT / "engine/termin-scene/include/termin/bindings/tc_value_helpers.hpp",
        REPO_ROOT / "engine/termin-scene/include/termin/soa/soa_type.hpp",
        REPO_ROOT / "core/termin-inspect/include/termin/inspect/tc_kind.hpp",
        REPO_ROOT / "core/termin-inspect/include/termin/inspect/tc_kind_cpp_ext.hpp",
        REPO_ROOT / "graphics/termin-graphics/include/tgfx/tgfx_material_handle.hpp",
    ]
    removed_app_paths = [
        app_cpp_root / "bindings/entity/entity_bindings.hpp",
        app_cpp_root / "bindings/geom",
        app_cpp_root / "bindings/tc_value_helpers.hpp",
        app_cpp_root / "bindings/trent_helpers.hpp",
        app_cpp_root / "core/identifiable.hpp",
        app_cpp_root / "entity/cmp_ref.hpp",
        app_cpp_root / "entity_bindings.hpp",
        app_cpp_root / "geom_bindings.cpp",
        app_cpp_root / "inspect/tc_kind.hpp",
        app_cpp_root / "inspect/tc_kind_cpp_ext.hpp",
        app_cpp_root / "material/tc_material_handle.hpp",
        app_cpp_root / "pch.hpp",
        app_cpp_root / "render/render.hpp",
        app_cpp_root / "sdl_bindings.hpp",
        app_cpp_root / "soa",
        app_cpp_root / "tc_viewport_bindings.hpp",
    ]
    allowed_first_level_dirs = {
        "bindings",
        "editor",
        "navmesh",
        "render",
    }

    assert [path for path in canonical_paths if not path.exists()] == []
    assert [path for path in removed_app_paths if path.exists()] == []

    unexpected: list[str] = []
    for path in app_cpp_root.iterdir():
        if path.is_dir() and path.name not in allowed_first_level_dirs:
            unexpected.append(str(path.relative_to(REPO_ROOT)))
        elif path.is_file():
            unexpected.append(str(path.relative_to(REPO_ROOT)))

    assert unexpected == []


def test_sdk_cli_entrypoints_are_outside_app_cxx_package() -> None:
    app_cpp_app = REPO_ROOT / "editor/termin-app/cpp/app"
    cli_root = REPO_ROOT / "editor/termin-cli"
    cli_sources = [
        cli_root / "src/termin.cpp",
        cli_root / "src/termin_builder.cpp",
        cli_root / "src/termin_runner.cpp",
        cli_root / "src/termin_modules_cli.cpp",
        cli_root / "src/termin_stdlib.cpp",
        cli_root / "src/termin_python_backend.hpp",
    ]
    removed_app_paths = [
        app_cpp_app / "termin.cpp",
        app_cpp_app / "termin_builder.cpp",
        app_cpp_app / "termin_runner.cpp",
        app_cpp_app / "termin_modules_cli.cpp",
        app_cpp_app / "termin_stdlib.cpp",
        app_cpp_app / "termin_python_backend.hpp",
    ]

    assert (cli_root / "CMakeLists.txt").is_file()
    assert [path for path in cli_sources if not path.is_file()] == []
    assert [path for path in removed_app_paths if path.exists()] == []

    app_cmake = _read_text(REPO_ROOT / "editor/termin-app/cpp/CMakeLists.txt")
    forbidden_fragments = (
        "add_executable(termin\n",
        "add_executable(termin_builder",
        "add_executable(termin_runner",
        "add_executable(termin_modules_cli",
        "add_executable(termin_stdlib",
    )
    offenders = [fragment for fragment in forbidden_fragments if fragment in app_cmake]
    assert offenders == []


def test_app_scene_rendering_facade_is_removed() -> None:
    app_facade = REPO_ROOT / "editor/termin-app/termin/scene_rendering.py"

    assert not app_facade.exists()


def test_app_default_preloaders_compat_layer_is_removed() -> None:
    app_facade = REPO_ROOT / "editor/termin-app/termin/editor_core/default_preloaders.py"

    assert not app_facade.exists()


def test_app_scene_cache_is_removed() -> None:
    assert not (REPO_ROOT / "editor/termin-app/termin/cache").exists()

    offenders: list[str] = []
    source_roots = [
        REPO_ROOT / "editor/termin-app/termin",
        REPO_ROOT / "physics/termin-navmesh/python/termin",
    ]
    forbidden_fragments = (
        "termin.cache",
        "SceneCache",
        "scene_cache",
    )

    for root in source_roots:
        for path in root.rglob("*.py"):
            text = _read_text(path)
            for fragment in forbidden_fragments:
                if fragment in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {fragment}")

    assert offenders == []


def test_project_helpers_are_outside_app_package() -> None:
    assert not (REPO_ROOT / "editor/termin-app/termin/project").exists()
    assert not (REPO_ROOT / "editor/termin-app/termin/project_build").exists()
    assert (REPO_ROOT / "editor/termin-project/python/termin/project").is_dir()
    assert (REPO_ROOT / "editor/termin-project-build/python/termin/project_build").is_dir()


def test_project_creation_and_default_scene_are_outside_app_package() -> None:
    assert not (REPO_ROOT / "editor/termin-app/termin/default_scene.py").exists()
    assert (REPO_ROOT / "editor/termin-project/python/termin/project/creation.py").is_file()

    source_roots = [
        REPO_ROOT / "editor/termin-app/termin",
        REPO_ROOT / "editor/termin-app/tests",
    ]
    forbidden_fragments = (
        "termin.default_scene",
        "from termin.launcher.recent import RecentProjects, create_project",
    )

    offenders: list[str] = []
    for root in source_roots:
        for path in root.rglob("*.py"):
            if path == Path(__file__):
                continue
            text = _read_text(path)
            for fragment in forbidden_fragments:
                if fragment in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {fragment}")

    assert offenders == []


def test_serialization_kind_facade_is_removed_from_app_package() -> None:
    assert not (REPO_ROOT / "editor/termin-app/termin/serialization/__init__.py").exists()
    assert not (REPO_ROOT / "editor/termin-app/termin/serialization/kind.py").exists()
    assert (REPO_ROOT / "core/termin-inspect/python/termin/inspect/kind.py").is_file()

    source_roots = [
        REPO_ROOT / "editor/termin-app/termin",
        REPO_ROOT / "editor/termin-app/tests",
        REPO_ROOT / "engine/termin-bootstrap",
    ]
    forbidden_fragments = (
        "termin.serialization",
        "from termin.serialization",
    )

    offenders: list[str] = []
    for root in source_roots:
        for path in root.rglob("*.py"):
            if path == Path(__file__):
                continue
            text = _read_text(path)
            for fragment in forbidden_fragments:
                if fragment in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {fragment}")

    assert offenders == []


def test_top_level_app_utility_facades_are_removed() -> None:
    assert not (REPO_ROOT / "editor/termin-app/termin/util.py").exists()
    assert not (REPO_ROOT / "editor/termin-app/termin/core").exists()
    assert not (REPO_ROOT / "editor/termin-app/termin/log.py").exists()
    assert (REPO_ROOT / "core/termin-base/python/termin/geombase/quaternion.py").is_file()

    source_roots = [
        REPO_ROOT / "editor/termin-app/termin",
        REPO_ROOT / "editor/termin-app/tests",
    ]
    forbidden_fragments = (
        "termin.util",
        "from termin.util",
        "termin.core",
        "from termin.core",
        "termin.log",
        "from termin import log",
    )

    offenders: list[str] = []
    for root in source_roots:
        for path in root.rglob("*.py"):
            if path == Path(__file__):
                continue
            text = _read_text(path)
            for fragment in forbidden_fragments:
                if fragment in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {fragment}")

    assert offenders == []


def test_glb_scene_animation_repair_is_outside_app_package() -> None:
    assert not (REPO_ROOT / "editor/termin-app/termin/scene_animation_repair.py").exists()
    assert (
        REPO_ROOT
        / "editor/termin-glb-adapters/python/termin/glb_adapters/scene_animation_repair.py"
    ).is_file()

    source_roots = [
        REPO_ROOT / "editor/termin-app/termin",
        REPO_ROOT / "editor/termin-player/termin",
        REPO_ROOT / "editor/termin-project-build/python/termin",
    ]
    forbidden_fragments = (
        "termin.scene_animation_repair",
        "from termin import scene_animation_repair",
    )

    offenders: list[str] = []
    for root in source_roots:
        for path in root.rglob("*.py"):
            text = _read_text(path)
            for fragment in forbidden_fragments:
                if fragment in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {fragment}")

    assert offenders == []


def test_glb_package_does_not_import_editor_core() -> None:
    source_roots = [
        REPO_ROOT / "graphics/termin-glb/python",
        REPO_ROOT / "graphics/termin-glb/tests",
    ]
    forbidden_fragments = (
        "termin.editor_core",
        "from termin.editor_core",
    )

    offenders: list[str] = []
    for root in source_roots:
        for path in root.rglob("*.py"):
            text = _read_text(path)
            for fragment in forbidden_fragments:
                if fragment in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {fragment}")

    assert offenders == []


def test_domain_package_tests_do_not_import_editor_private_modules() -> None:
    source_roots = [
        path / "tests"
        for path in _package_roots()
        if path != REPO_ROOT / "editor/termin-app" and (path / "tests").is_dir()
    ]
    source_roots.extend(sorted(REPO_ROOT.glob("engine/termin-components/*/tests")))
    forbidden_fragments = (
        "termin.editor_core",
        "termin.launcher",
    )

    offenders: list[str] = []
    for root in source_roots:
        for path in root.rglob("*.py"):
            text = _read_text(path)
            for fragment in forbidden_fragments:
                if fragment in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {fragment}")

    assert offenders == []


def test_framegraph_automation_service_is_toolkit_neutral() -> None:
    canonical = REPO_ROOT / "editor/termin-app/termin/editor_core/framegraph_debugger_service.py"
    python_model = REPO_ROOT / "editor/termin-app/termin/editor_core/framegraph_debugger_model.py"
    native_debugger = REPO_ROOT / "engine/termin-engine/include/termin/render/frame_graph_debugger.hpp"

    assert not python_model.exists()
    assert canonical.is_file()
    assert native_debugger.is_file()
    source = _read_text(canonical)
    assert "tcgui" not in source
    assert "FrameGraphDebugTarget" not in source
    assert "reset_capture" not in source


def test_launcher_controller_is_toolkit_neutral() -> None:
    controller = REPO_ROOT / "editor/termin-app/termin/launcher/controller.py"

    assert controller.is_file()
    source = _read_text(controller)
    assert "tcgui" not in source
    assert "termin.gui_native" not in source


def test_editor_utility_dialog_policy_is_toolkit_neutral() -> None:
    shared_models = (
        "about_model.py",
        "audio_debugger_model.py",
        "python_console_model.py",
        "project_settings_model.py",
        "project_build_controller.py",
        "build_profiles_model.py",
        "navigation_settings_model.py",
        "settings_model.py",
        "scene_settings_model.py",
        "scene_manager_model.py",
        "scene_file_controller.py",
        "game_mode_session_connectors.py",
        "editor_scene_session.py",
        "render_scene_session.py",
        "spacemouse_settings_model.py",
        "undo_history_model.py",
    )
    for filename in shared_models:
        source = _read_text(REPO_ROOT / "editor/termin-app/termin/editor_core" / filename)
        assert "tcgui" not in source
        assert "editor_native" not in source

    frontend_sources = (
        "editor/termin-app/termin/editor_native/about_dialog.py",
        "editor/termin-app/termin/editor_native/python_console.py",
        "editor/termin-app/termin/editor_native/project_settings_dialog.py",
        "editor/termin-app/termin/editor_native/navigation_settings_dialogs.py",
        "editor/termin-app/termin/editor_native/settings_dialog.py",
        "editor/termin-app/termin/editor_native/diagnostic_dialogs.py",
        "editor/termin-app/termin/editor_native/scene_settings_dialogs.py",
        "editor/termin-app/termin/editor_native/scene_manager_dialog.py",
        "editor/termin-app/termin/editor_native/spacemouse_settings_dialog.py",
    )
    for path in frontend_sources:
        assert "termin.editor_core" in _read_text(REPO_ROOT / path)


def test_domain_python_tests_are_outside_app_tests_package() -> None:
    moved_tests = {
        "termin-app/tests/aabb_test.py": "termin-components/termin-components-kinematic/tests/aabb_test.py",
        "termin-app/tests/asset_plugin_test.py": "termin-default-assets/tests/asset_plugin_test.py",
        "termin-app/tests/collider_test.py": "termin-collision/tests/collider_test.py",
        "termin-app/tests/framegraph_test.py": "termin-render/tests/framegraph_test.py",
        "termin-app/tests/pathfinding_test.py": "termin-navmesh/tests/pathfinding_test.py",
        "termin-app/tests/pose2_test.py": "termin-base/tests/python/pose2_test.py",
        "termin-app/tests/pose_test.py": "termin-base/tests/python/pose_test.py",
        "termin-app/tests/shader_parser_test.py": "termin-materials/tests/test_shader_parser.py",
        "termin-app/tests/test_canonical_animation_imports.py": (
            "termin-animation/tests/test_canonical_animation_imports.py"
        ),
        "termin-app/tests/test_collision_teleport_component.py": (
            "termin-collision/tests/test_collision_teleport_component.py"
        ),
        "termin-app/tests/test_component_frame_pass_registries.py": (
            "termin-default-assets/tests/test_component_frame_pass_registries.py"
        ),
        "termin-app/tests/test_default_pipeline_specs.py": (
            "termin-engine/tests/test_default_pipeline_specs.py"
        ),
        "termin-app/tests/test_edge_flipping.py": "termin-navmesh/tests/test_edge_flipping.py",
        "termin-app/tests/test_funnel_algorithm.py": "termin-navmesh/tests/test_funnel_algorithm.py",
        "termin-app/tests/test_general_pose3.py": "termin-base/tests/python/test_general_pose3.py",
        "termin-app/tests/test_general_transform3.py": (
            "termin-components/termin-components-kinematic/tests/test_general_transform3.py"
        ),
        "termin-app/tests/test_gltf_loader.py": "termin-glb/tests/test_glb_loader.py",
        "termin-app/tests/test_material_asset_texture_persistence.py": (
            "termin-default-assets/tests/test_material_asset_texture_persistence.py"
        ),
        "termin-app/tests/test_material_pass_serialization.py": (
            "termin-components/termin-components-render/tests/python/test_material_pass_serialization.py"
        ),
        "termin-app/tests/test_material_registry_copy.py": (
            "termin-materials/tests/test_material_registry_copy.py"
        ),
        "termin-app/tests/test_mesh_spec_defaults.py": (
            "termin-default-assets/tests/test_mesh_spec_defaults.py"
        ),
        "termin-app/tests/test_navmesh_package_facade.py": (
            "termin-navmesh/tests/test_navmesh_package_facade.py"
        ),
        "termin-app/tests/test_procedural_mesh_component.py": (
            "termin-components/termin-components-mesh/tests/test_procedural_mesh_component.py"
        ),
        "termin-app/tests/test_project_build_capabilities.py": (
            "termin-project-build/tests/test_project_build_capabilities.py"
        ),
        "termin-app/tests/test_project_build_context.py": (
            "termin-project-build/tests/test_project_build_context.py"
        ),
        "termin-app/tests/test_project_build_diagnostics.py": (
            "termin-project-build/tests/test_project_build_diagnostics.py"
        ),
        "termin-app/tests/test_project_build_pipeline.py": (
            "termin-project-build/tests/test_project_build_pipeline.py"
        ),
        "termin-app/tests/test_project_build_profile_backend.py": (
            "termin-project-build/tests/test_project_build_profile_backend.py"
        ),
        "termin-app/tests/test_project_build_target_common.py": (
            "termin-project-build/tests/test_project_build_target_common.py"
        ),
        "termin-app/tests/test_project_build_target_preflight.py": (
            "termin-project-build/tests/test_project_build_target_preflight.py"
        ),
        "termin-app/tests/test_project_settings.py": "termin-project/tests/test_project_settings.py",
        "termin-app/tests/test_runtime_package_exporter.py": (
            "termin-project-build/tests/test_runtime_package_exporter.py"
        ),
        "termin-app/tests/test_runtime_package_exporter_android.py": (
            "termin-project-build/tests/test_runtime_package_exporter_android.py"
        ),
        "termin-app/tests/test_runtime_package_validator.py": (
            "termin-project-build/tests/test_runtime_package_validator.py"
        ),
        "termin-app/tests/test_scene_rendering_lifecycle.py": (
            "termin-engine/tests/test_scene_rendering_lifecycle.py"
        ),
        "termin-app/tests/test_screen_point_to_ray.py": (
            "termin-components/termin-components-render/tests/python/test_screen_point_to_ray.py"
        ),
        "termin-app/tests/test_texture_lazy_registration.py": (
            "termin-default-assets/tests/test_texture_lazy_registration.py"
        ),
        "termin-app/tests/util_test.py": "termin-base/tests/python/util_test.py",
    }

    missing_targets = [
        target for target in moved_tests.values()
        if not _owned_path(target).is_file()
    ]
    remaining_sources = [
        source for source in moved_tests
        if _owned_path(source).exists()
    ]

    assert missing_targets == []
    assert remaining_sources == []


def test_project_modules_runtime_is_outside_app_package() -> None:
    assert not (REPO_ROOT / "editor/termin-app/termin/modules").exists()
    assert not (REPO_ROOT / "editor/termin-app/termin/module_warmup.py").exists()
    assert (REPO_ROOT / "editor/termin-project-modules/python/termin/project_modules/runtime.py").is_file()
    assert (REPO_ROOT / "editor/termin-project-modules/python/termin/project_modules/warmup.py").is_file()

    source_roots = [
        REPO_ROOT / "editor/termin-app/termin",
        REPO_ROOT / "editor/termin-player/termin",
        REPO_ROOT / "editor/termin-app/cpp/app",
    ]
    forbidden_fragments = (
        "termin.modules.runtime",
        "termin.module_warmup",
    )

    offenders: list[str] = []
    for root in source_roots:
        for path in root.rglob("*"):
            if path == Path(__file__):
                continue
            if path.suffix not in {".py", ".cpp", ".hpp", ".h"}:
                continue
            text = _read_text(path)
            for fragment in forbidden_fragments:
                if fragment in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {fragment}")

    assert offenders == []


def test_stdlib_resources_are_outside_app_package() -> None:
    assert not (REPO_ROOT / "editor/termin-app/termin/resources/stdlib").exists()
    assert (REPO_ROOT / "engine/termin-stdlib/python/termin/stdlib/resources").is_dir()

    source_roots = [
        REPO_ROOT / "editor/termin-app/termin",
        REPO_ROOT / "editor/termin-app/cpp/app",
        REPO_ROOT / "editor/termin-app/tests",
    ]
    forbidden_fragments = (
        'Path(termin.__path__[0]) / "resources" / "stdlib"',
        "termin-app/termin/resources/stdlib",
        "termin/resources/stdlib",
    )

    offenders: list[str] = []
    for root in source_roots:
        for path in root.rglob("*"):
            if path == Path(__file__):
                continue
            if path.suffix not in {".py", ".cpp", ".hpp", ".h"}:
                continue
            text = _read_text(path)
            for fragment in forbidden_fragments:
                if fragment in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {fragment}")

    assert offenders == []


def test_legacy_project_builder_and_build_json_player_path_are_removed() -> None:
    assert not (REPO_ROOT / "editor/termin-app/termin/project_builder").exists()

    source_roots = [
        REPO_ROOT / "editor/termin-app/termin",
        REPO_ROOT / "editor/termin-player/termin",
        REPO_ROOT / "editor/termin-app/cpp/app",
    ]
    forbidden_fragments = (
        "termin.project_builder",
        "legacy-dev-export",
        "legacy-build",
        "build_json_path",
    )

    offenders: list[str] = []
    for root in source_roots:
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".cpp", ".hpp", ".h"}:
                continue
            text = _read_text(path)
            for fragment in forbidden_fragments:
                if fragment in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {fragment}")

    assert offenders == []


def test_python_compatibility_reexport_modules_stay_removed() -> None:
    source_roots = [*_package_roots(), REPO_ROOT / "graphics/tcplot"]

    offenders: list[str] = []
    for root in source_roots:
        if "termin-thirdparty" in root.parts:
            continue
        for path in root.rglob("*.py"):
            if path == Path(__file__):
                continue
            if any(part in {"build", "sdk", ".venv", "__pycache__"} for part in path.parts):
                continue
            if "Compatibility re-export" in _read_text(path):
                offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []
