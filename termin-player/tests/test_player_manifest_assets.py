from pathlib import Path

from termin.player.runtime import load_manifest_assets_with_import_plugins
from termin_assets import AssetTypeRegistry, PreLoadResult


class RecordingResourceManager:
    def __init__(self) -> None:
        self.results: list[PreLoadResult] = []

    def register_file(self, result: PreLoadResult) -> None:
        self.results.append(result)


class FakeImportPlugin:
    extensions: set[str] = set()

    def __init__(self, type_id: str, *, priority: int) -> None:
        self.type_id = type_id
        self.priority = priority

    def preload(self, path: str) -> PreLoadResult:
        return PreLoadResult(
            resource_type=self.type_id,
            path=path,
            uuid=f"{Path(path).stem}-uuid",
        )


def test_manifest_loader_uses_supplied_import_registry(tmp_path: Path) -> None:
    alpha = tmp_path / "assets" / "alpha.asset"
    alpha.parent.mkdir(parents=True)
    alpha.write_text("alpha", encoding="utf-8")
    beta = tmp_path / "assets" / "beta.asset"
    beta.write_text("beta", encoding="utf-8")

    registry = AssetTypeRegistry()
    registry.register_import(FakeImportPlugin("beta_asset", priority=20))
    registry.register_import(FakeImportPlugin("alpha_asset", priority=10))

    rm = RecordingResourceManager()
    resources = [
        {
            "kind": "asset",
            "type": "beta_asset",
            "build_path": "assets/beta.asset",
        },
        {
            "kind": "asset",
            "type": "alpha_asset",
            "build_path": "assets/alpha.asset",
        },
        {
            "kind": "asset",
            "type": "scene",
            "build_path": "assets/main.scene",
        },
        {
            "kind": "asset",
            "type": "unknown_asset",
            "build_path": "assets/unknown.asset",
        },
    ]

    loaded_count = load_manifest_assets_with_import_plugins(
        project_path=tmp_path,
        resources=resources,
        resource_manager=rm,
        import_registry=registry,
    )

    assert loaded_count == 2
    assert [result.resource_type for result in rm.results] == [
        "alpha_asset",
        "beta_asset",
    ]
    assert [result.uuid for result in rm.results] == [
        "alpha-uuid",
        "beta-uuid",
    ]
