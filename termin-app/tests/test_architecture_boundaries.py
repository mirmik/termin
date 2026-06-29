from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def test_scene_owns_component_ref_and_entity_binding_helpers() -> None:
    scene_component_ref_binding = (
        REPO_ROOT / "termin-scene/include/termin/bindings/tc_component_ref_bindings.hpp"
    )
    scene_entity_helpers = REPO_ROOT / "termin-scene/include/termin/bindings/entity_helpers.hpp"
    app_duplicate_paths = [
        REPO_ROOT / "termin-app/cpp/termin/entity/tc_component_ref.hpp",
        REPO_ROOT / "termin-app/cpp/termin/bindings/entity/entity_helpers.hpp",
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
        REPO_ROOT / "termin-app/cpp",
        REPO_ROOT / "termin-scene",
        *sorted(REPO_ROOT.glob("termin-components/*")),
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
        for path in REPO_ROOT.glob("termin-*/**/*")
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
    canonical_header = REPO_ROOT / "termin-voxels/termin/voxels/voxel_grid_handle.hpp"
    app_compat_header = REPO_ROOT / "termin-app/cpp/termin/assets/voxel_grid_handle.hpp"
    forbidden_includes = (
        '#include "termin/assets/voxel_grid_handle.hpp"',
        "#include <termin/assets/voxel_grid_handle.hpp>",
    )
    source_roots = [
        REPO_ROOT / "termin-app/cpp",
        REPO_ROOT / "termin-voxels",
        *sorted(REPO_ROOT.glob("termin-components/*")),
        REPO_ROOT / "termin-bootstrap",
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
    app_cpp_root = REPO_ROOT / "termin-app/cpp/termin"
    canonical_paths = [
        REPO_ROOT / "termin-base/python/bindings/geom/geom_module.cpp",
        REPO_ROOT / "termin-scene/include/termin/entity/cmp_ref.hpp",
        REPO_ROOT / "termin-scene/include/termin/bindings/entity_bindings.hpp",
        REPO_ROOT / "termin-scene/include/termin/bindings/tc_value_helpers.hpp",
        REPO_ROOT / "termin-scene/include/termin/soa/soa_type.hpp",
        REPO_ROOT / "termin-inspect/include/termin/inspect/tc_kind.hpp",
        REPO_ROOT / "termin-inspect/include/termin/inspect/tc_kind_cpp_ext.hpp",
        REPO_ROOT / "termin-graphics/include/tgfx/tgfx_material_handle.hpp",
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


def test_app_scene_rendering_facade_is_removed() -> None:
    app_facade = REPO_ROOT / "termin-app/termin/scene_rendering.py"

    assert not app_facade.exists()


def test_app_default_preloaders_compat_layer_is_removed() -> None:
    app_facade = REPO_ROOT / "termin-app/termin/editor_core/default_preloaders.py"

    assert not app_facade.exists()


def test_app_scene_cache_is_removed() -> None:
    assert not (REPO_ROOT / "termin-app/termin/cache").exists()

    offenders: list[str] = []
    source_roots = [
        REPO_ROOT / "termin-app/termin",
        REPO_ROOT / "termin-navmesh/python/termin",
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
    assert not (REPO_ROOT / "termin-app/termin/project").exists()
    assert not (REPO_ROOT / "termin-app/termin/project_build").exists()
    assert (REPO_ROOT / "termin-project/python/termin/project").is_dir()
    assert (REPO_ROOT / "termin-project-build/python/termin/project_build").is_dir()


def test_glb_scene_animation_repair_is_outside_app_package() -> None:
    assert not (REPO_ROOT / "termin-app/termin/scene_animation_repair.py").exists()
    assert (REPO_ROOT / "termin-glb/python/termin/glb/scene_animation_repair.py").is_file()

    source_roots = [
        REPO_ROOT / "termin-app/termin",
        REPO_ROOT / "termin-player/termin",
        REPO_ROOT / "termin-project-build/python/termin",
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


def test_project_modules_runtime_is_outside_app_package() -> None:
    assert not (REPO_ROOT / "termin-app/termin/modules").exists()
    assert not (REPO_ROOT / "termin-app/termin/module_warmup.py").exists()
    assert (REPO_ROOT / "termin-project-modules/python/termin/project_modules/runtime.py").is_file()
    assert (REPO_ROOT / "termin-project-modules/python/termin/project_modules/warmup.py").is_file()

    source_roots = [
        REPO_ROOT / "termin-app/termin",
        REPO_ROOT / "termin-player/termin",
        REPO_ROOT / "termin-app/cpp/app",
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
    assert not (REPO_ROOT / "termin-app/termin/resources/stdlib").exists()
    assert (REPO_ROOT / "termin-stdlib/python/termin/stdlib/resources").is_dir()

    source_roots = [
        REPO_ROOT / "termin-app/termin",
        REPO_ROOT / "termin-app/cpp/app",
        REPO_ROOT / "termin-app/tests",
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
    assert not (REPO_ROOT / "termin-app/termin/project_builder").exists()

    source_roots = [
        REPO_ROOT / "termin-app/termin",
        REPO_ROOT / "termin-player/termin",
        REPO_ROOT / "termin-app/cpp/app",
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
