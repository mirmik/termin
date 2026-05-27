from math import isclose

from termin.csg import (
    ProceduralMeshDocument,
    evaluate_document,
    extrude,
    make_box,
    to_mesh3,
)
from termin.csg.cad import box, circle, mesh, rect
from termin.csg.cad_state import CadState, load_cad_state, save_cad_state
from termin.csg.document_raycast import ray_plane_intersection, raycast_document
from termin.csg.procedural_document import ProceduralPlane
from termin.csg.viewer_camera import OrbitCamera


def test_native_primitives_and_extrude_are_importable_from_python():
    solid = make_box(2.0, 3.0, 4.0)

    assert solid.status == "No Error"
    assert not solid.is_empty
    assert solid.triangle_count == 12
    assert isclose(solid.volume, 24.0)

    profile = [
        (-2.0, -2.0),
        (2.0, -2.0),
        (2.0, 2.0),
        (-2.0, 2.0),
    ]
    hole = [
        (-0.5, -0.5),
        (0.5, -0.5),
        (0.5, 0.5),
        (-0.5, 0.5),
    ]
    extruded = extrude(profile, 2.0, holes=[hole])

    assert extruded.status == "No Error"
    assert not extruded.is_empty
    assert isclose(extruded.volume, 30.0)

    result_mesh = to_mesh3(extruded, "python-extrude")
    assert result_mesh.is_valid()
    assert result_mesh.has_normals()


def test_script_cad_layer_composes_profiles_and_solids():
    frame = (rect(4.0, 4.0) - circle(0.5, segments=32)).extrude(1.5)
    cut = box(1.0, 1.0, 4.0)
    result = frame - cut

    assert result.status == "No Error"
    assert not result.is_empty
    assert result.volume < frame.volume

    result_mesh = mesh(result, "cad-result", flat_shading=True)
    assert result_mesh.is_valid()
    assert result_mesh.has_normals()


def test_procedural_document_roundtrip_evaluates_extrude_operation():
    document = ProceduralMeshDocument()
    contour = document.add_contour_from_points(
        [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
        ]
    )
    assert contour is not None

    sketch_id = document.find_sketch_id_for_contour(contour.id)
    operation = document.add_extrude_operation_for_sketch(sketch_id, height=3.0)
    assert operation is not None

    restored = ProceduralMeshDocument.from_dict(document.to_dict())
    evaluated = evaluate_document(restored)

    assert len(evaluated) == 1
    assert evaluated[0].operation_id == operation.id
    assert evaluated[0].contour_id == contour.id
    assert isclose(evaluated[0].solid.volume, 12.0)
    assert evaluated[0].point_transform((1.0, 1.0, 3.0)) == (1.0, 1.0, 3.0)


def test_document_raycast_uses_evaluated_solids_in_document_space():
    document = ProceduralMeshDocument()
    contour = document.add_contour_from_points(
        [
            (-1.0, -1.0, 0.0),
            (1.0, -1.0, 0.0),
            (1.0, 1.0, 0.0),
            (-1.0, 1.0, 0.0),
        ]
    )
    assert contour is not None

    sketch_id = document.find_sketch_id_for_contour(contour.id)
    operation = document.add_extrude_operation_for_sketch(sketch_id, height=2.0)
    assert operation is not None

    hit = raycast_document(document, (0.0, 0.0, 5.0), (0.0, 0.0, -1.0))

    assert hit is not None
    assert hit.operation_id == operation.id
    assert hit.contour_id == contour.id
    assert isclose(hit.point[0], 0.0, abs_tol=1.0e-6)
    assert isclose(hit.point[1], 0.0, abs_tol=1.0e-6)
    assert isclose(hit.point[2], 2.0, abs_tol=1.0e-6)
    assert hit.normal == (0.0, 0.0, 1.0)


def test_ray_plane_intersection_reports_parallel_and_behind_rays():
    plane = ProceduralPlane()

    assert ray_plane_intersection((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), plane) is None
    assert ray_plane_intersection((0.0, 0.0, 1.0), (0.0, 0.0, 1.0), plane) is None

    point = ray_plane_intersection((0.0, 0.0, 1.0), (0.0, 0.0, -2.0), plane)
    assert point == (0.0, 0.0, 0.0)


def test_cad_state_roundtrip_preserves_document_camera_and_selection(tmp_path):
    document = ProceduralMeshDocument()
    contour = document.add_contour_from_points(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ]
    )
    assert contour is not None

    sketch_id = document.find_sketch_id_for_contour(contour.id)
    operation = document.add_extrude_operation_for_sketch(sketch_id, height=2.0)
    assert operation is not None

    camera = OrbitCamera()
    camera.target = (3.0, 4.0, 5.0)
    camera.distance = 12.0
    camera.yaw = 0.25
    camera.pitch = 0.5

    saved_path = save_cad_state(
        tmp_path / "shape",
        CadState.from_app_state(document, camera, ("operation", operation.id)),
    )
    restored = load_cad_state(saved_path)

    assert saved_path.name == "shape.tcsg.json"
    assert restored.document.contour_count() == 1
    assert restored.selection == ("operation", operation.id)
    assert restored.camera.target == (3.0, 4.0, 5.0)
    assert isclose(restored.camera.distance, 12.0)
    assert isclose(restored.camera.yaw, 0.25, abs_tol=1.0e-6)
    assert isclose(restored.camera.pitch, 0.5, abs_tol=1.0e-6)


def test_cad_viewer_builds_auxiliary_geometry_for_immediate_renderer():
    from termin.csg.cad_viewer import build_document_immediate_geometry, build_reference_geometry

    reference = build_reference_geometry()
    assert len(reference.lines or []) == 45

    document = ProceduralMeshDocument()
    contour = document.add_contour_from_points(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ]
    )
    assert contour is not None

    sketch_id = document.find_sketch_id_for_contour(contour.id)
    operation = document.add_extrude_operation_for_sketch(sketch_id, height=1.0)
    assert operation is not None

    geometry = build_document_immediate_geometry(document, None, ("operation", operation.id))
    vertices: list[tuple[float, float, float]] = []
    geometry.collect_vertices(vertices)

    assert len(geometry.lines or []) > 0
    assert len(vertices) > 0
    assert all(line.color == (0.85, 1.0, 1.0, 1.0) for line in geometry.lines or [])
