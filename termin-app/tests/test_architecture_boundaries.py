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
