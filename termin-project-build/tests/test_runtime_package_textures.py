import json
from pathlib import Path

from termin.project_build.runtime_package.textures import (
    collect_material_texture_refs,
    write_textures,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_runtime_texture_export_copies_source_and_import_settings(tmp_path: Path) -> None:
    project = tmp_path / "project"
    source_path = project / "Textures" / "Albedo.png"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"PNG source bytes")
    _write_json(
        Path(f"{source_path}.meta"),
        {
            "uuid": "albedo-uuid",
            "flip_x": True,
            "flip_y": False,
            "transpose": True,
        },
    )

    package_dir = tmp_path / "package"
    resources: list[dict[str, str]] = []
    diagnostics = []
    write_textures(
        project,
        package_dir,
        {"albedo-uuid": "Albedo"},
        resources,
        diagnostics,
    )

    assert diagnostics == []
    assert resources == [
        {
            "type": "texture",
            "uuid": "albedo-uuid",
            "path": "textures/albedo-uuid.texture.json",
        }
    ]
    assert (package_dir / "textures" / "albedo-uuid.png").read_bytes() == b"PNG source bytes"
    assert json.loads((package_dir / "textures" / "albedo-uuid.texture.json").read_text(encoding="utf-8")) == {
        "uuid": "albedo-uuid",
        "name": "Albedo",
        "source_path": "textures/albedo-uuid.png",
        "import_settings": {
            "flip_x": True,
            "flip_y": False,
            "transpose": True,
        },
    }


def test_runtime_texture_export_reports_missing_or_unsupported_source(tmp_path: Path) -> None:
    project = tmp_path / "project"
    unsupported_path = project / "Textures" / "Albedo.dds"
    unsupported_path.parent.mkdir(parents=True)
    unsupported_path.write_bytes(b"DDS")
    _write_json(Path(f"{unsupported_path}.meta"), {"uuid": "unsupported-uuid"})

    resources: list[dict[str, str]] = []
    diagnostics = []
    write_textures(
        project,
        tmp_path / "package",
        {"missing-uuid": "Missing", "unsupported-uuid": "Unsupported"},
        resources,
        diagnostics,
    )

    assert resources == []
    assert [(item.level, item.path, item.message) for item in diagnostics] == [
        (
            "error",
            "Textures/Albedo.dds",
            "Runtime exporter does not support texture source format '.dds' for UUID 'unsupported-uuid'",
        ),
        (
            "error",
            "textures/missing-uuid.texture.json",
            "Runtime exporter could not export texture because no project texture source with UUID 'missing-uuid' was found",
        ),
    ]


def test_runtime_texture_export_rejects_formats_missing_from_runtime_codec_contract(tmp_path: Path) -> None:
    project = tmp_path / "project"
    source_path = project / "Textures" / "Legacy.tga"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"TGA")
    _write_json(Path(f"{source_path}.meta"), {"uuid": "legacy-uuid"})

    resources: list[dict[str, str]] = []
    diagnostics = []
    write_textures(
        project,
        tmp_path / "package",
        {"legacy-uuid": "Legacy"},
        resources,
        diagnostics,
    )

    assert resources == []
    assert len(diagnostics) == 1
    assert diagnostics[0].message == (
        "Runtime exporter does not support texture source format '.tga' for UUID 'legacy-uuid'"
    )


def test_material_texture_reference_collection_excludes_builtins() -> None:
    references: dict[str, str] = {}
    diagnostics = []

    collect_material_texture_refs(
        {
            "textures": {
                "u_albedo": {"kind": "asset", "uuid": "albedo-uuid", "name": "Albedo"},
                "u_normal": {"kind": "builtin", "name": "normal"},
            }
        },
        references,
        diagnostics,
        "materials/example.tmat.json",
    )

    assert diagnostics == []
    assert references == {"albedo-uuid": "Albedo"}
