import importlib.util

from termin.editor_core.registry_sources import (
    ResourceAssetSource,
    ResourceComponentSource,
    NavMeshRegistrySource,
    SceneRegistrySource,
    WatchedFileSource,
    build_resource_manager_pages,
)
from termin.editor_core.registry_viewer_model import RegistryCollectionController


def test_migrated_tcgui_registry_viewer_modules_stay_removed():
    for module_name in (
        "termin.editor_tcgui.dialogs.core_registry_viewer",
        "termin.editor_tcgui.dialogs.inspect_registry_viewer",
        "termin.editor_tcgui.dialogs.navmesh_registry_viewer",
        "termin.editor_tcgui.dialogs.registry_viewer_dialog",
        "termin.editor_tcgui.dialogs.resource_manager_viewer",
    ):
        assert importlib.util.find_spec(module_name) is None


class FakeAsset:
    def __init__(self, name: str, uuid: str | None = None, source_path: str | None = None):
        self.name = name
        self.uuid = uuid or f"uuid-{name}"
        self.source_path = source_path or f"Assets/{name}.asset"
        self.is_loaded = False
        self.version = 3
        self.load_count = 0

    def ensure_loaded(self):
        self.is_loaded = True
        self.load_count += 1


class FakeComponent:
    pass


class FakeResourceManager:
    def __init__(self):
        self.assets = {"mesh": {"uuid-cube": FakeAsset("cube")}}

    def iter_runtime_assets(self, type_id):
        return tuple(self.assets.get(type_id, {}).values())

    def get_runtime_asset_by_uuid(self, type_id, uuid):
        return self.assets.get(type_id, {}).get(uuid)

    def list_component_names(self):
        return ["FakeComponent"]

    def get_component(self, name):
        return FakeComponent if name == "FakeComponent" else None


def test_resource_asset_source_uses_public_runtime_api_and_loads_on_activation():
    manager = FakeResourceManager()
    source = ResourceAssetSource(manager, "mesh")
    row = tuple(source.load_rows())[0]

    assert row.stable_id == "uuid-cube"
    assert row.cells == ("cube", "not loaded", "3", "uuid-cube")
    source.activate(row)
    assert manager.assets["mesh"]["uuid-cube"].load_count == 1
    assert tuple(source.load_rows())[0].cells[1] == "loaded"


def test_resource_asset_source_lists_filters_and_activates_duplicate_names_by_uuid():
    manager = FakeResourceManager()
    first = FakeAsset("shared", "uuid-first", "Assets/One/shared.asset")
    second = FakeAsset("shared", "uuid-second", "Assets/Two/shared.asset")
    manager.assets["mesh"] = {first.uuid: first, second.uuid: second}
    source = ResourceAssetSource(manager, "mesh")

    rows = tuple(source.load_rows())

    assert [row.stable_id for row in rows] == ["uuid-first", "uuid-second"]
    assert [row.cells[0] for row in rows] == [
        "shared — Assets/One/shared.asset",
        "shared — Assets/Two/shared.asset",
    ]
    assert all("shared" in row.details for row in rows)
    controller = RegistryCollectionController(source)
    controller.refresh()
    filtered = controller.set_filter("shared")
    assert [row.stable_id for row in filtered.rows] == ["uuid-first", "uuid-second"]
    source.activate(rows[1])
    assert first.load_count == 0
    assert second.load_count == 1


def test_resource_manager_pages_and_component_source_are_toolkit_neutral():
    manager = FakeResourceManager()
    pages = build_resource_manager_pages(manager)
    assert [page.stable_id for page in pages] == [
        "material",
        "shader",
        "mesh",
        "texture",
        "voxel_grid",
        "navmesh",
        "skeleton",
        "pipeline",
        "components",
    ]
    component_row = tuple(ResourceComponentSource(manager).load_rows())[0]
    assert component_row.stable_id == "FakeComponent"
    assert "FakeResourceManager" not in component_row.details


class FakeProcessor:
    resource_type = "mesh"
    extensions = {".obj", ".stl"}

    def get_tracked_files(self):
        return {"/project/Assets/cube.obj": {"cube"}}


class FakeWatcher:
    project_path = "/project"
    watched_dirs = {"/project", "/project/Assets"}
    is_enabled = True

    def get_file_count(self):
        return 1

    def get_all_files_count(self):
        return 3

    def get_all_files_by_extension(self):
        return {".obj": 1, ".py": 2}

    def get_all_processors(self):
        return [FakeProcessor()]


def test_watched_file_source_builds_extension_directory_and_processor_hierarchy():
    rows = tuple(WatchedFileSource(FakeWatcher()).load_rows())
    by_id = {row.stable_id: row for row in rows}
    assert by_id["watcher/extensions/.obj"].parent_id == "watcher/extensions"
    assert by_id["watcher/directories//project/Assets"].parent_id == "watcher/directories"
    tracked = by_id["watcher/processors/mesh//project/Assets/cube.obj"]
    assert tracked.parent_id == "watcher/processors/mesh"
    assert "cube" in tracked.details


def test_scene_registry_source_preserves_scene_entity_hierarchy(monkeypatch):
    from termin.engine import scene as engine_scene

    handle = (7, 2)
    monkeypatch.setattr(
        engine_scene,
        "tc_scene_registry_get_all_info",
        lambda: [{"handle": handle, "name": "Main", "entity_count": 2}],
    )
    monkeypatch.setattr(
        engine_scene,
        "tc_scene_get_entities",
        lambda _handle: [
            {
                "name": "Child",
                "uuid": "child-uuid",
                "id_index": 2,
                "id_generation": 1,
                "parent_index": 1,
                "parent_generation": 1,
                "components": [{"type_name": "MeshRenderer", "enabled": True}],
            },
            {
                "name": "Parent",
                "uuid": "parent-uuid",
                "id_index": 1,
                "id_generation": 1,
                "parent_index": None,
                "parent_generation": None,
                "components": [],
            },
        ],
    )
    monkeypatch.setattr(
        engine_scene,
        "tc_scene_get_component_types",
        lambda _handle: [{"type_name": "MeshRenderer", "count": 1}],
    )

    rows = tuple(SceneRegistrySource().load_rows())
    by_name = {row.cells[0]: row for row in rows}
    assert by_name["Parent"].parent_id == by_name["Main"].stable_id
    assert by_name["Child"].parent_id == by_name["Parent"].stable_id
    assert "MeshRenderer" in by_name["Child"].details


class FakeNavMesh:
    name = "runtime-navmesh"
    cell_size = 0.25
    origin = (0.0, 0.0, 0.0)

    def polygon_count(self):
        return 5

    def triangle_count(self):
        return 8

    def vertex_count(self):
        return 12


class FakeEntity:
    name = "Nav Source"
    uuid = "entity-uuid"


class FakeNavMeshRegistry:
    def list_agent_types(self):
        return ["Human"]

    def get_all(self, agent_type):
        assert agent_type == "Human"
        return [(FakeNavMesh(), FakeEntity())]


def test_navmesh_registry_source_uses_public_instance_snapshot(monkeypatch):
    from termin.navmesh.registry import NavMeshRegistry

    monkeypatch.setattr(
        NavMeshRegistry,
        "instances",
        classmethod(lambda _cls: (("scene-uuid", FakeNavMeshRegistry()),)),
    )
    rows = tuple(NavMeshRegistrySource().load_rows())
    assert [row.cells[0] for row in rows] == [
        "Scene: scene-uuid",
        "Human",
        "Nav Source",
    ]
    assert rows[2].parent_id == rows[1].stable_id
    assert "Triangles: 8" in rows[2].details
