from termin.navmesh.registry import NavMeshRegistry


class FakeScene:
    def __init__(self, uuid: str):
        self.uuid = uuid


def test_navmesh_registry_instances_returns_sorted_snapshot():
    NavMeshRegistry.clear_instance("scene-a")
    NavMeshRegistry.clear_instance("scene-b")
    second = NavMeshRegistry.for_scene(FakeScene("scene-b"))
    first = NavMeshRegistry.for_scene(FakeScene("scene-a"))
    try:
        assert NavMeshRegistry.instances() == (("scene-a", first), ("scene-b", second))
    finally:
        NavMeshRegistry.clear_instance("scene-a")
        NavMeshRegistry.clear_instance("scene-b")
