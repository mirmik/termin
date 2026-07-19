from termin.csg.document_edit import set_contour_point
from termin.csg.procedural_document import ProceduralPlane
from termin.mesh.procedural_mesh_component import ProceduralMeshComponent


class _MeshComponent:
    def __init__(self):
        self.mesh = None
        self.set_mesh_count = 0
        self.mesh_is_generated = False
        self.notify_mesh_changed_count = 0

    def set_generated_mesh(self, mesh):
        self.mesh = mesh
        self.mesh_is_generated = True
        self.set_mesh_count += 1

    def notify_mesh_changed(self):
        self.notify_mesh_changed_count += 1


class _TestProceduralMeshComponent(ProceduralMeshComponent):
    def __init__(self, mesh_component):
        super().__init__(auto_regenerate=False)
        self._test_mesh_component = mesh_component

    def _mesh_component(self):
        return self._test_mesh_component


def test_procedural_mesh_component_updates_existing_tc_mesh_on_regenerate():
    mesh_component = _MeshComponent()
    component = _TestProceduralMeshComponent(mesh_component)
    contour = component.document.add_contour_on_plane_from_points(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
        ],
        ProceduralPlane(),
    )
    assert contour is not None
    sketch_id = component.document.find_sketch_id_for_contour(contour.id)
    assert sketch_id is not None
    operation = component.document.add_extrude_operation_for_sketch(sketch_id, height=1.0)
    assert operation is not None

    assert component.regenerate() is True
    first_mesh = mesh_component.mesh
    assert first_mesh is not None
    first_uuid = first_mesh.uuid
    first_vertex_count = first_mesh.vertex_count
    assert mesh_component.set_mesh_count == 1

    assert set_contour_point(component.document, contour.id, 2, (1.5, 1.25)) is True
    component.mark_dirty()

    assert component.regenerate() is True
    assert mesh_component.mesh is first_mesh
    assert mesh_component.mesh.uuid == first_uuid
    assert mesh_component.mesh.vertex_count == first_vertex_count
    assert mesh_component.set_mesh_count == 1
    assert mesh_component.notify_mesh_changed_count == 1
