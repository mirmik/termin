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
from termin.csg.document_tree_model import build_document_tree
from termin.csg.document_edit import set_contour_point, set_sketch_plane
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
    assert operation.params["vector"] == [0.0, 0.0, 3.0]

    restored = ProceduralMeshDocument.from_dict(document.to_dict())
    evaluated = evaluate_document(restored)

    assert len(evaluated) == 1
    assert evaluated[0].operation_id == operation.id
    assert evaluated[0].contour_id == contour.id
    assert isclose(evaluated[0].solid.volume, 12.0)
    assert evaluated[0].point_transform((1.0, 1.0, 3.0)) == (1.0, 1.0, 3.0)


def test_procedural_document_extrudes_along_oblique_and_downward_vectors():
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
    operation = document.add_extrude_operation_for_sketch(sketch_id, vector=(0.5, 0.25, -2.0))
    assert operation is not None

    evaluated = evaluate_document(document)
    assert len(evaluated) == 1

    result_mesh = to_mesh3(evaluated[0].solid, "oblique-extrude", "", True)
    transformed = [
        evaluated[0].point_transform((float(vertex[0]), float(vertex[1]), float(vertex[2])))
        for vertex in result_mesh.vertices
    ]
    xs = [point[0] for point in transformed]
    ys = [point[1] for point in transformed]
    zs = [point[2] for point in transformed]

    assert isclose(min(zs), -2.0, abs_tol=1.0e-6)
    assert isclose(max(zs), 0.0, abs_tol=1.0e-6)
    assert isclose(max(xs), 1.5, abs_tol=1.0e-6)
    assert isclose(max(ys), 1.25, abs_tol=1.0e-6)


def test_procedural_document_boolean_operations_evaluate_as_root_operations():
    document = ProceduralMeshDocument()
    first = document.add_contour_from_points(
        [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
        ]
    )
    second = document.add_contour_from_points(
        [
            (1.0, 0.0, 0.0),
            (3.0, 0.0, 0.0),
            (3.0, 2.0, 0.0),
            (1.0, 2.0, 0.0),
        ]
    )
    assert first is not None
    assert second is not None

    first_sketch_id = document.find_sketch_id_for_contour(first.id)
    second_sketch_id = document.find_sketch_id_for_contour(second.id)
    first_extrude = document.add_extrude_operation_for_sketch(first_sketch_id, height=1.0)
    second_extrude = document.add_extrude_operation_for_sketch(second_sketch_id, height=1.0)
    assert first_extrude is not None
    assert second_extrude is not None

    union = document.add_boolean_operation("union", [first_extrude.id, second_extrude.id])
    assert union is not None

    evaluated = evaluate_document(document)
    assert len(evaluated) == 1
    assert evaluated[0].operation_id == union.id
    assert isclose(evaluated[0].solid.volume, 6.0, abs_tol=1.0e-6)

    roots = build_document_tree(document)
    assert len(roots) == 1
    assert roots[0].kind == "operation"
    assert roots[0].item_id == union.id
    assert roots[0].text.startswith("[Union]")
    assert len(roots[0].children) == 2


def test_procedural_document_boolean_subtract_and_intersect_volumes():
    document = ProceduralMeshDocument()
    first = document.add_contour_from_points(
        [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
        ]
    )
    second = document.add_contour_from_points(
        [
            (1.0, 0.0, 0.0),
            (3.0, 0.0, 0.0),
            (3.0, 2.0, 0.0),
            (1.0, 2.0, 0.0),
        ]
    )
    assert first is not None
    assert second is not None
    first_op = document.add_extrude_operation_for_sketch(document.find_sketch_id_for_contour(first.id), height=1.0)
    second_op = document.add_extrude_operation_for_sketch(document.find_sketch_id_for_contour(second.id), height=1.0)
    assert first_op is not None
    assert second_op is not None

    subtract_op = document.add_boolean_operation("subtract", [first_op.id, second_op.id])
    assert subtract_op is not None
    evaluated = evaluate_document(document)
    assert len(evaluated) == 1
    assert isclose(evaluated[0].solid.volume, 2.0, abs_tol=1.0e-6)

    document.operations.pop()
    intersect_op = document.add_boolean_operation("intersect", [first_op.id, second_op.id])
    assert intersect_op is not None
    evaluated = evaluate_document(document)
    assert len(evaluated) == 1
    assert isclose(evaluated[0].solid.volume, 2.0, abs_tol=1.0e-6)


def test_procedural_document_subtracts_downward_extrude_as_cutting_tool():
    document = ProceduralMeshDocument()
    base = document.add_contour_from_points(
        [
            (-1.0, -1.0, 0.0),
            (1.0, -1.0, 0.0),
            (1.0, 1.0, 0.0),
            (-1.0, 1.0, 0.0),
        ]
    )
    assert base is not None
    base_op = document.add_extrude_operation_for_sketch(
        document.find_sketch_id_for_contour(base.id),
        height=1.0,
    )
    assert base_op is not None

    cutter = document.add_contour_on_plane_from_points(
        [
            (-0.4, -0.4, 1.0),
            (0.4, -0.4, 1.0),
            (0.4, 0.4, 1.0),
            (-0.4, 0.4, 1.0),
        ],
        ProceduralPlane(origin=(0.0, 0.0, 1.0)),
    )
    assert cutter is not None
    cutter_op = document.add_extrude_operation_for_sketch(
        document.find_sketch_id_for_contour(cutter.id),
        vector=(0.0, 0.0, -0.5),
    )
    assert cutter_op is not None
    subtract_op = document.add_boolean_operation("subtract", [base_op.id, cutter_op.id])
    assert subtract_op is not None

    evaluated = evaluate_document(document)
    assert len(evaluated) == 1
    assert isclose(evaluated[0].solid.volume, 3.68, abs_tol=1.0e-6)


def test_set_sketch_plane_updates_contour_document_space_points():
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

    assert set_sketch_plane(
        document,
        sketch_id,
        ProceduralPlane(
            origin=(0.0, 0.0, 2.0),
            x_axis=(0.0, 1.0, 0.0),
            y_axis=(1.0, 0.0, 0.0),
        ),
    )
    sketch = document.find_sketch(sketch_id)
    assert sketch is not None
    points = sketch.contour_points(contour)
    assert points[0] == (0.0, 0.0, 2.0)
    assert points[2] == (1.0, 1.0, 2.0)


def test_set_contour_point_updates_local_contour_coordinates():
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

    assert set_contour_point(document, contour.id, 2, (2.0, 1.5))
    assert contour.points[2] == (2.0, 1.5)
    assert not set_contour_point(document, contour.id, 99, (0.0, 0.0))
    assert not set_contour_point(document, "missing", 0, (0.0, 0.0))


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


def test_cad_app_operation_parameter_panel_updates_extrude_vector():
    from termin.csg.cad_app import CadApp

    app = CadApp()
    app._build_operation_params_panel()
    contour = app.document.add_contour_from_points(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ]
    )
    assert contour is not None

    sketch_id = app.document.find_sketch_id_for_contour(contour.id)
    operation = app.document.add_extrude_operation_for_sketch(sketch_id, height=1.0)
    assert operation is not None

    app.selected_node_data = ("operation", operation.id)
    app._refresh_operation_params_panel()
    assert app.operation_params_panel.visible is True
    assert app.extrude_vector_inputs["z"].value == 1.0

    app.extrude_vector_inputs["x"].value = 0.25
    app.extrude_vector_inputs["z"].value = -2.0
    app._on_extrude_vector_changed(-2.0)

    assert operation.params["vector"] == [0.25, 0.0, -2.0]


def test_cad_app_plane_parameter_panel_updates_sketch_plane():
    from termin.csg.cad_app import CadApp

    app = CadApp()
    app._build_plane_params_panel()
    contour = app.document.add_contour_from_points(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ]
    )
    assert contour is not None

    sketch_id = app.document.find_sketch_id_for_contour(contour.id)
    app.selected_node_data = ("plane", sketch_id)
    app._refresh_plane_params_panel()
    assert app.plane_params_panel.visible is True
    assert app.plane_inputs["origin.z"].value == 0.0

    app.plane_inputs["origin.z"].value = 2.5
    app._on_plane_param_changed(2.5)

    sketch = app.document.find_sketch(sketch_id)
    assert sketch is not None
    assert sketch.plane.origin == (0.0, 0.0, 2.5)


def test_cad_app_contour_parameter_panel_updates_contour_points():
    from termin.csg.cad_app import CadApp

    app = CadApp()
    app._build_contour_params_panel()
    contour = app.document.add_contour_from_points(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ]
    )
    assert contour is not None

    app.selected_node_data = ("contour", contour.id)
    app._refresh_contour_params_panel()
    assert app.contour_params_panel.visible is True
    assert app.contour_point_inputs[(2, "x")].value == 1.0
    assert app.contour_point_inputs[(2, "y")].value == 1.0

    app.contour_point_inputs[(2, "x")].value = 1.75
    app.contour_point_inputs[(2, "y")].value = 1.25
    app._on_contour_point_changed(2, "y", 1.25)

    assert contour.points[2] == (1.75, 1.25)


def test_cad_app_wireframe_toggle_updates_preview_state():
    from termin.csg.cad_app import CadApp

    app = CadApp()
    assert app.show_wireframe is True
    assert app.preview_revision == 0

    app._on_wireframe_changed(False)

    assert app.show_wireframe is False
    assert app.preview_revision == 1
    assert app.dirty is True


def test_cad_viewer_builds_auxiliary_geometry_for_immediate_renderer():
    from termin.csg.cad_viewer import build_document_immediate_geometry, build_reference_geometry

    reference = build_reference_geometry()
    assert len(reference.lines or []) == 45
    assert all(line.depth_test for line in reference.lines or [])

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

    without_wireframe = build_document_immediate_geometry(
        document,
        None,
        ("operation", operation.id),
        show_wireframe=False,
    )
    assert without_wireframe.lines == []
