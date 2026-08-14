from __future__ import annotations

import json
from pathlib import Path
import shutil

import termin.project_build.android_runtime_assets as android_runtime_assets


def _bundled_smoke_assets() -> Path:
    return Path(__file__).parents[3] / "platform" / "termin-android" / "assets"


def _fake_builtin_contract(package_dir: Path) -> dict[str, object]:
    builtin_dir = package_dir / "builtin_shaders"
    builtin_dir.mkdir(parents=True, exist_ok=True)
    (builtin_dir / "engine-shader-catalog.json").write_text(
        json.dumps(
            {
                "version": 1,
                "shaders": [
                    {
                        "uuid": "termin-engine-test",
                        "name": "Test",
                        "language": "slang",
                        "stages": {
                            "fragment": {
                                "path": "termin-engine-test.frag.slang",
                                "entry": "fs_main",
                            }
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (builtin_dir / "termin-engine-test.frag.slang").write_text(
        "void fs_main() {}\n", encoding="utf-8"
    )
    artifact = package_dir / "shaders/vulkan/termin-engine-test.frag.spv"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"SPV")
    return {
        "version": 1,
        "catalog": "builtin_shaders/engine-shader-catalog.json",
        "shaders": [
            {
                "uuid": "termin-engine-test",
                "artifacts": {
                    "vulkan": {
                        "fragment": "shaders/vulkan/termin-engine-test.frag.spv"
                    }
                },
            }
        ],
    }


def test_bundled_android_triangle_matches_its_authored_shader_contract() -> None:
    assets = _bundled_smoke_assets()
    mesh = json.loads(
        (assets / "meshes/android-triangle.tmesh.json").read_text(encoding="utf-8")
    )
    shader = json.loads(
        (assets / "shaders/termin-android-scene-color.shader.json").read_text(
            encoding="utf-8"
        )
    )

    mesh_attributes = {item["name"]: item for item in mesh["layout"]}
    required_inputs = {
        item["semantic"]: item
        for item in shader["shader_contract"]["vertex_inputs"]
        if item.get("required", True)
    }
    assert set(required_inputs) == {"position", "color"}
    assert set(required_inputs) <= set(mesh_attributes)
    assert all(
        required_inputs[name]["type"] == mesh_attributes[name]["components"]
        for name in required_inputs
    )


def test_prepare_android_runtime_assets_generates_missing_builtin_closure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    shutil.copytree(_bundled_smoke_assets(), source)
    compiler = tmp_path / "termin_shaderc"
    compiler.write_text("compiler", encoding="utf-8")

    def fake_write(package_dir, diagnostics, shader_compiler, requested_targets):
        assert Path(shader_compiler) == compiler
        assert requested_targets == ("vulkan",)
        assert diagnostics == []
        return _fake_builtin_contract(package_dir)

    monkeypatch.setattr(
        android_runtime_assets,
        "write_default_pipeline_shader_artifacts",
        fake_write,
    )

    output = tmp_path / "prepared"
    result = android_runtime_assets.prepare_android_runtime_assets(
        source, output, compiler
    )

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert result.generated_builtin_shader_contract is True
    assert manifest["builtin_shader_contract"]["catalog"] == (
        "builtin_shaders/engine-shader-catalog.json"
    )
    assert (output / "shaders/vulkan/termin-engine-test.frag.spv").is_file()
    assert not (source / "builtin_shaders").exists()


def test_prepare_android_runtime_assets_preserves_complete_package(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    shutil.copytree(_bundled_smoke_assets(), source)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["builtin_shader_contract"] = _fake_builtin_contract(source)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def unexpected_generation(*args, **kwargs):
        raise AssertionError("complete runtime package must not be regenerated")

    monkeypatch.setattr(
        android_runtime_assets,
        "write_default_pipeline_shader_artifacts",
        unexpected_generation,
    )

    output = tmp_path / "prepared"
    result = android_runtime_assets.prepare_android_runtime_assets(
        source, output, tmp_path / "missing-compiler"
    )

    assert result.generated_builtin_shader_contract is False
    assert (output / "builtin_shaders/engine-shader-catalog.json").is_file()
