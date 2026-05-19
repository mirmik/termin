from pathlib import Path

from termin.assets.default_plugins import register_default_import_asset_plugins
from termin.player.runtime import load_manifest_assets_with_import_plugins
from termin_assets import AssetTypeRegistry, PreLoadResult


class RecordingResourceManager:
    def __init__(self) -> None:
        self.results: list[PreLoadResult] = []

    def register_file(self, result: PreLoadResult) -> None:
        self.results.append(result)


def _default_import_registry() -> AssetTypeRegistry:
    registry = AssetTypeRegistry()
    register_default_import_asset_plugins(registry)
    return registry


def test_manifest_loader_uses_resource_type_import_plugins(tmp_path: Path) -> None:
    texture = tmp_path / "assets" / "Textures" / "Albedo.png"
    texture.parent.mkdir(parents=True)
    texture.write_bytes(b"png")
    texture.with_name(texture.name + ".meta").write_text(
        '{"uuid": "texture-uuid"}',
        encoding="utf-8",
    )
    audio = tmp_path / "assets" / "Audio" / "Hit.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"wav")
    audio.with_name(audio.name + ".meta").write_text(
        '{"uuid": "audio-uuid"}',
        encoding="utf-8",
    )
    glsl = tmp_path / "assets" / "Shaders" / "lighting.glsl"
    glsl.parent.mkdir(parents=True)
    glsl.write_text("// include", encoding="utf-8")
    glsl.with_name(glsl.name + ".meta").write_text(
        '{"uuid": "glsl-uuid"}',
        encoding="utf-8",
    )
    shader = tmp_path / "assets" / "Shaders" / "Standard.shader"
    shader.write_text("shader", encoding="utf-8")
    shader.with_name(shader.name + ".meta").write_text(
        '{"uuid": "shader-uuid"}',
        encoding="utf-8",
    )
    material = tmp_path / "assets" / "Materials" / "Default.material"
    material.parent.mkdir(parents=True)
    material.write_text(
        '{"uuid": "material-uuid", "shader": "Standard"}',
        encoding="utf-8",
    )

    rm = RecordingResourceManager()
    resources = [
        {
            "kind": "asset",
            "type": "texture",
            "build_path": "assets/Textures/Albedo.png",
        },
        {
            "kind": "asset",
            "type": "audio_clip",
            "build_path": "assets/Audio/Hit.wav",
        },
        {
            "kind": "asset",
            "type": "glsl",
            "build_path": "assets/Shaders/lighting.glsl",
        },
        {
            "kind": "asset",
            "type": "shader",
            "build_path": "assets/Shaders/Standard.shader",
        },
        {
            "kind": "asset",
            "type": "material",
            "build_path": "assets/Materials/Default.material",
        },
        {
            "kind": "asset",
            "type": "pipeline",
            "build_path": "assets/Pipelines/Test.pipeline",
        },
        {
            "kind": "asset",
            "type": "scene",
            "build_path": "assets/Scenes/Main.scene",
        },
    ]

    loaded_count = load_manifest_assets_with_import_plugins(
        project_path=tmp_path,
        resources=resources,
        resource_manager=rm,
        import_registry=_default_import_registry(),
    )

    assert loaded_count == 5
    assert [result.resource_type for result in rm.results] == [
        "glsl",
        "shader",
        "audio_clip",
        "texture",
        "material",
    ]
    assert [result.uuid for result in rm.results] == [
        "glsl-uuid",
        "shader-uuid",
        "audio-uuid",
        "texture-uuid",
        "material-uuid",
    ]
