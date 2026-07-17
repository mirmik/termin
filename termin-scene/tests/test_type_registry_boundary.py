from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = (
    REPOSITORY_ROOT / "termin-scene" / "include",
    REPOSITORY_ROOT / "termin-scene" / "src",
    REPOSITORY_ROOT / "termin-scene" / "cpp",
    REPOSITORY_ROOT / "termin-render" / "include",
    REPOSITORY_ROOT / "termin-render" / "src",
    REPOSITORY_ROOT / "termin-csharp" / "src",
)
SOURCE_SUFFIXES = {".c", ".cpp", ".h", ".hpp"}
LEGACY_TOKENS = ("tc_type_registry", "tc_type_entry", "type_version", "registry_node")


def test_component_and_pass_types_use_only_common_runtime_records() -> None:
    assert not (REPOSITORY_ROOT / "termin-scene/include/tc_type_registry.h").exists()
    assert not (REPOSITORY_ROOT / "termin-scene/src/tc_type_registry.c").exists()

    violations = []
    for root in PRODUCTION_ROOTS:
        for source in sorted(root.rglob("*")):
            if source.suffix not in SOURCE_SUFFIXES:
                continue
            text = source.read_text(encoding="utf-8")
            for token in LEGACY_TOKENS:
                if token in text:
                    violations.append(
                        f"{source.relative_to(REPOSITORY_ROOT)} contains {token}"
                    )

    assert violations == []
