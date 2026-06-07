from math import isclose

from termin.csg import (
    CsgEditorController,
    OPERATION_KIND_WALL,
    ProceduralMeshDocument,
    document_to_mesh3,
    document_to_tc_mesh,
    evaluate_document,
    extrude,
    make_box,
    operation_spec,
    ordered_boolean_operation_specs,
    ordered_primitive_specs,
    primitive_spec,
    to_mesh3,
)
from termin.csg.cad import box, circle, mesh, rect
from termin.csg.csg_editor_panel import CsgEditorPanel
from termin.csg.cad_state import CadState, load_cad_state, save_cad_state
from termin.csg.cad_viewer import build_document_solid_meshes, document_bounds
from termin.csg.document_raycast import ray_plane_intersection, raycast_document
from termin.csg.document_tree_model import build_document_tree
from termin.csg.document_visual_model import PATH_SELECTED_COLOR, build_document_visual_model
from termin.csg.document_edit import (
    add_boolean_input,
    finish_draft_path,
    move_boolean_input,
    remove_boolean_input,
    set_contour_point,
    set_path_point,
    set_sketch_plane,
    set_wall_corner_offset,
    start_sketch_draft,
)
from termin.csg.procedural_document import CONTOUR_ROLE_HOLE, CONTOUR_ROLE_OUTER, ProceduralPlane
from termin.csg.sketch_point_interaction import pick_selected_sketch_point
from termin.csg.viewer_camera import OrbitCamera


def _test_editor_panel(controller: CsgEditorController) -> CsgEditorPanel:
    panel = CsgEditorPanel(
        controller,
        lambda result, default_status="": result.success,
        log_prefix="[CsgEditorPanelTest]",
    )
    panel.build()
    return panel


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


def test_procedural_document_extrudes_outer_contours_with_holes():
    document = ProceduralMeshDocument()
    outer = document.add_contour_from_points(
        [
            (0.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
            (4.0, 4.0, 0.0),
            (0.0, 4.0, 0.0),
        ]
    )
    assert outer is not None

    sketch_id = document.find_sketch_id_for_contour(outer.id)
    hole = document.add_contour_to_sketch_from_points(
        sketch_id,
        [
            (1.0, 1.0, 0.0),
            (3.0, 1.0, 0.0),
            (3.0, 3.0, 0.0),
            (1.0, 3.0, 0.0),
        ],
        role=CONTOUR_ROLE_HOLE,
        parent_contour_id=outer.id,
    )
    assert hole is not None
    assert outer.role == CONTOUR_ROLE_OUTER
    assert hole.parent_contour_id == outer.id

    operation = document.add_extrude_operation_for_sketch(sketch_id, height=2.0)
    assert operation is not None
    assert operation.inputs == [outer.id]

    evaluated = evaluate_document(document)
    assert len(evaluated) == 1
    assert evaluated[0].contour_id == outer.id
    assert isclose(evaluated[0].solid.volume, 24.0, abs_tol=1.0e-6)

    roots = build_document_tree(document)
    assert len(roots) == 1
    sketch_node = roots[0].children[0]
    outer_node = sketch_node.children[1]
    assert outer_node.text.startswith("[Outer]")
    assert len(outer_node.children) == 1
    assert outer_node.children[0].text.startswith("[Hole]")


def test_procedural_document_stores_open_sketch_paths_separately_from_contours():
    document = ProceduralMeshDocument()
    path = document.add_path_on_plane_from_points(
        [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 1.0, 0.0),
        ],
        ProceduralPlane(),
        purpose="wall",
    )

    assert path is not None
    assert document.contour_count() == 0
    assert document.path_count() == 1
    sketch_id = document.find_sketch_id_for_path(path.id)
    assert sketch_id
    path_ref = document.find_path_ref(path.id)
    assert path_ref is not None
    sketch, restored_path = path_ref
    assert restored_path.closed is False
    assert sketch.path_points(restored_path)[1] == (2.0, 0.0, 0.0)

    restored = ProceduralMeshDocument.from_dict(document.to_dict())
    assert restored.path_count() == 1
    restored_ref = restored.find_path_ref(path.id)
    assert restored_ref is not None
    assert restored_ref[1].purpose == "wall"


def test_finish_draft_path_requires_two_points_and_selects_path():
    document = ProceduralMeshDocument()
    draft = start_sketch_draft(plane=ProceduralPlane(), purpose="wall")
    draft.points = [(0.0, 0.0, 0.0)]

    failed = finish_draft_path(document, draft, purpose="wall")

    assert failed.success is False
    assert document.path_count() == 0

    draft.points.append((1.0, 0.0, 0.0))
    result = finish_draft_path(document, draft, purpose="wall")

    assert result.success is True
    assert result.selection is not None
    assert result.selection[0] == "path"
    assert result.path is not None
    assert result.path.closed is False
    assert document.path_count() == 1
    assert draft.points == []


def test_document_tree_and_visual_model_show_open_paths():
    document = ProceduralMeshDocument()
    path = document.add_path_on_plane_from_points(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
        ],
        ProceduralPlane(),
        purpose="wall",
    )
    assert path is not None

    roots = build_document_tree(document)
    assert "[Path]" in roots[0].children[1].text

    visual = build_document_visual_model(document, selected_node_data=("path", path.id))
    selected = visual.polylines[-1]
    assert selected.closed is False
    assert selected.points == [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]


def test_procedural_document_evaluates_wall_operation_from_open_path():
    document = ProceduralMeshDocument()
    path = document.add_path_on_plane_from_points(
        [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
        ],
        ProceduralPlane(),
        purpose="wall",
    )
    assert path is not None
    sketch_id = document.find_sketch_id_for_path(path.id)

    operation = document.add_wall_operation_for_sketch(
        sketch_id,
        height=3.0,
        thickness=0.5,
        alignment="center",
    )

    assert operation is not None
    assert operation.kind == OPERATION_KIND_WALL
    assert operation.inputs == [path.id]
    evaluated = evaluate_document(document)
    assert len(evaluated) == 1
    assert evaluated[0].operation_id == operation.id
    assert evaluated[0].contour_id == path.id
    assert isclose(evaluated[0].solid.volume, 3.0, abs_tol=1.0e-6)

    roots = build_document_tree(document)
    assert len(roots) == 1
    assert roots[0].text.startswith("[Wall]")
    assert roots[0].children[0].text.startswith("[Sketch]")


def test_procedural_document_evaluates_variable_height_wall_from_open_path():
    document = ProceduralMeshDocument()
    path = document.add_path_on_plane_from_points(
        [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
        ],
        ProceduralPlane(),
        purpose="wall",
    )
    assert path is not None
    sketch_id = document.find_sketch_id_for_path(path.id)
    operation = document.add_wall_operation_for_sketch(
        sketch_id,
        height=3.0,
        thickness=0.5,
        alignment="center",
    )
    assert operation is not None

    assert set_wall_corner_offset(document, operation.id, path.id, 1, 2.0)
    restored = ProceduralMeshDocument.from_dict(document.to_dict())
    restored_operation = restored.find_operation(operation.id)
    assert restored_operation is not None
    assert restored_operation.params["corner_height_offsets"][path.id] == [0.0, 2.0]

    evaluated = evaluate_document(restored)
    assert len(evaluated) == 1
    assert evaluated[0].contour_id == path.id
    assert isclose(evaluated[0].solid.volume, 4.0, abs_tol=1.0e-6)

    visual = build_document_visual_model(restored, selected_node_data=("operation", operation.id))
    handle_points = [point.point for point in visual.points if point.color == (0.36, 0.72, 1.0, 1.0)]
    assert (0.0, 0.0, 3.0) in handle_points
    assert (2.0, 0.0, 5.0) in handle_points


def test_wall_corner_offset_rejects_non_positive_effective_height():
    document = ProceduralMeshDocument()
    path = document.add_path_on_plane_from_points(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
        ],
        ProceduralPlane(),
        purpose="wall",
    )
    assert path is not None
    sketch_id = document.find_sketch_id_for_path(path.id)
    operation = document.add_wall_operation_for_sketch(sketch_id, height=2.0, thickness=0.2)
    assert operation is not None

    assert not set_wall_corner_offset(document, operation.id, path.id, 0, -2.0)
    assert "corner_height_offsets" not in operation.params


def test_wall_operation_selection_exposes_source_path_points_for_dragging():
    document = ProceduralMeshDocument()
    path = document.add_path_on_plane_from_points(
        [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
        ],
        ProceduralPlane(),
        purpose="wall",
    )
    assert path is not None
    sketch_id = document.find_sketch_id_for_path(path.id)
    operation = document.add_wall_operation_for_sketch(sketch_id, height=3.0, thickness=0.2)
    assert operation is not None

    drag = pick_selected_sketch_point(
        document,
        ("operation", operation.id),
        lambda point: (point[0] * 100.0, point[1] * 100.0),
        200.0,
        0.0,
    )

    assert drag is not None
    assert drag.kind == "path"
    assert drag.item_id == path.id
    assert drag.point_index == 1


def test_wall_operation_visual_model_highlights_source_path():
    document = ProceduralMeshDocument()
    path = document.add_path_on_plane_from_points(
        [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
        ],
        ProceduralPlane(),
        purpose="wall",
    )
    assert path is not None
    sketch_id = document.find_sketch_id_for_path(path.id)
    operation = document.add_wall_operation_for_sketch(sketch_id, height=3.0, thickness=0.2)
    assert operation is not None

    visual = build_document_visual_model(document, selected_node_data=("operation", operation.id))
    selected_paths = [polyline for polyline in visual.polylines if polyline.color == PATH_SELECTED_COLOR]

    assert len(selected_paths) == 1
    assert selected_paths[0].closed is False
    assert selected_paths[0].points == [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)]


def test_procedural_document_evaluates_wall_operation_from_contour_without_holes():
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

    operation = document.add_wall_operation_for_sketch(sketch_id, height=3.0, thickness=0.5)

    assert operation is not None
    assert operation.inputs == [contour.id]
    evaluated = evaluate_document(document)
    assert len(evaluated) == 1
    assert evaluated[0].contour_id == contour.id
    assert isclose(evaluated[0].solid.volume, 12.0, abs_tol=1.0e-6)


def test_procedural_document_rejects_extrude_for_sketch_with_open_paths():
    document = ProceduralMeshDocument()
    path = document.add_path_on_plane_from_points(
        [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
        ],
        ProceduralPlane(),
        purpose="wall",
    )
    assert path is not None
    sketch_id = document.find_sketch_id_for_path(path.id)

    operation = document.add_extrude_operation_for_sketch(sketch_id, height=1.0)

    assert operation is None


def test_procedural_document_evaluates_primitive_operations_and_booleans():
    document = ProceduralMeshDocument()
    box_operation = document.add_primitive_operation(
        "box",
        {
            "size": [4.0, 4.0, 2.0],
            "center": [0.0, 0.0, 0.0],
        },
    )
    cylinder_operation = document.add_primitive_operation(
        "cylinder",
        {
            "radius": 0.5,
            "height": 4.0,
            "center": [0.0, 0.0, 0.0],
            "rotation": [0.0, 90.0, 0.0],
            "circular_segments": 32,
        },
    )
    assert box_operation is not None
    assert cylinder_operation is not None

    subtract = document.add_boolean_operation("subtract", [box_operation.id, cylinder_operation.id])
    assert subtract is not None

    evaluated = evaluate_document(document)
    assert len(evaluated) == 1
    assert evaluated[0].operation_id == subtract.id
    assert evaluated[0].solid.volume < 32.0
    assert evaluated[0].solid.volume > 28.0

    roots = build_document_tree(document)
    assert roots[0].text.startswith("[Subtract]")
    assert roots[0].children[0].text.startswith("[Base] [Box]")
    assert roots[0].children[1].text.startswith("[Cut] [Cylinder]")


def test_operation_specs_drive_primitive_defaults_and_button_order():
    primitive_labels = [spec.label for spec in ordered_primitive_specs()]
    boolean_labels = [spec.label for spec in ordered_boolean_operation_specs()]
    assert primitive_labels == ["Box", "Sphere", "Cylinder", "Cone"]
    assert boolean_labels == ["Union", "Subtract", "Intersect"]

    box_spec = primitive_spec("box")
    wall_spec = operation_spec("wall")
    subtract_spec = operation_spec("subtract")
    assert box_spec is not None
    assert wall_spec is not None
    assert subtract_spec is not None
    assert [param.key for param in box_spec.param_schema] == [
        "size",
        "centered",
        "center",
        "rotation",
    ]
    assert subtract_spec.input_policy == "base_then_cutters"
    assert wall_spec.input_policy == "sketch_wall_sources"

    document = ProceduralMeshDocument()
    first = document.add_primitive_operation("box")
    second = document.add_primitive_operation("box")
    assert first is not None
    assert second is not None
    assert first.params["size"] == [1.0, 1.0, 1.0]
    assert first.params["center"] == [0.0, 0.0, 0.0]

    first.params["size"][0] = 7.0
    assert second.params["size"] == [1.0, 1.0, 1.0]


def test_document_tree_model_exposes_boolean_input_metadata():
    document = ProceduralMeshDocument()
    first = document.add_primitive_operation("box")
    second = document.add_primitive_operation("sphere")
    assert first is not None
    assert second is not None
    operation = document.add_boolean_operation("subtract", [first.id, second.id])
    assert operation is not None

    roots = build_document_tree(document)
    assert len(roots) == 1
    root = roots[0]
    assert root.item_id == operation.id
    assert root.accepts_drop_inside is True
    assert root.is_boolean_input is False

    base_node = root.children[0]
    cut_node = root.children[1]
    assert base_node.parent_operation_id == operation.id
    assert base_node.input_index == 0
    assert base_node.input_role == "[Base]"
    assert base_node.is_boolean_input is True
    assert base_node.accepts_drop_above_below is True
    assert cut_node.parent_operation_id == operation.id
    assert cut_node.input_index == 1
    assert cut_node.input_role == "[Cut]"


def test_cad_viewer_handles_empty_boolean_result_bounds():
    document = ProceduralMeshDocument()
    first = document.add_primitive_operation("box")
    second = document.add_primitive_operation("box")
    assert first is not None
    assert second is not None
    operation = document.add_boolean_operation("subtract", [first.id, second.id])
    assert operation is not None

    evaluated = evaluate_document(document)
    assert len(evaluated) == 1
    assert evaluated[0].solid.is_empty
    assert build_document_solid_meshes(document) == []

    lo, hi = document_bounds(document)
    assert tuple(float(v) for v in lo) == (-1.0, -1.0, -1.0)
    assert tuple(float(v) for v in hi) == (1.0, 1.0, 1.0)


def test_operation_transform_moves_extrude_and_boolean_results_after_evaluation():
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
    extrude_operation = document.add_extrude_operation_for_sketch(sketch_id, height=1.0)
    assert extrude_operation is not None
    extrude_operation.params["center"] = [5.0, 0.0, 0.0]

    evaluated = evaluate_document(document)
    assert len(evaluated) == 1
    assert evaluated[0].point_transform((0.0, 0.0, 0.0)) == (5.0, 0.0, 0.0)
    assert isclose(evaluated[0].solid.volume, 4.0, abs_tol=1.0e-6)

    box_operation = document.add_primitive_operation("box", {"size": [1.0, 1.0, 1.0]})
    assert box_operation is not None
    subtract_operation = document.add_boolean_operation("subtract", [extrude_operation.id, box_operation.id])
    assert subtract_operation is not None
    subtract_operation.params["center"] = [10.0, 0.0, 0.0]

    evaluated = evaluate_document(document)
    assert len(evaluated) == 1
    mesh = to_mesh3(evaluated[0].solid, "moved-subtract")
    xs = [float(vertex[0]) for vertex in mesh.vertices]
    assert min(xs) > 9.0


def test_document_mesh_converts_evaluated_root_solids_to_runtime_meshes():
    document = ProceduralMeshDocument()
    first = document.add_primitive_operation(
        "box",
        {
            "size": [2.0, 2.0, 2.0],
            "center": [-2.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 45.0],
        },
    )
    second = document.add_primitive_operation(
        "sphere",
        {
            "radius": 0.5,
            "center": [2.0, 0.0, 0.0],
            "circular_segments": 16,
        },
    )
    assert first is not None
    assert second is not None

    mesh3 = document_to_mesh3(document, "combined-csg")
    assert mesh3 is not None
    assert mesh3.is_valid()
    assert mesh3.has_normals()
    assert mesh3.vertex_count > 0
    assert mesh3.triangle_count > 0

    xs = [float(vertex[0]) for vertex in mesh3.vertices]
    assert min(xs) < -2.0
    assert max(xs) > 2.0

    tc_mesh = document_to_tc_mesh(document, "combined-csg")
    assert tc_mesh is not None
    assert tc_mesh.is_valid
    assert tc_mesh.vertex_count == mesh3.vertex_count
    assert tc_mesh.triangle_count == mesh3.triangle_count


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


def test_procedural_document_boolean_can_consume_later_operation_input():
    document = ProceduralMeshDocument()
    base = document.add_primitive_operation("box", {"size": [4.0, 4.0, 4.0]})
    first_cut = document.add_primitive_operation("box", {"size": [1.0, 1.0, 1.0], "center": [-1.0, 0.0, 0.0]})
    assert base is not None
    assert first_cut is not None
    subtract_op = document.add_boolean_operation("subtract", [base.id, first_cut.id])
    assert subtract_op is not None
    later_cut = document.add_primitive_operation("box", {"size": [1.0, 1.0, 1.0], "center": [1.0, 0.0, 0.0]})
    assert later_cut is not None

    assert add_boolean_input(document, subtract_op.id, later_cut.id)
    assert subtract_op.inputs == [base.id, first_cut.id, later_cut.id]

    evaluated = evaluate_document(document)
    assert len(evaluated) == 1
    assert evaluated[0].operation_id == subtract_op.id
    assert isclose(evaluated[0].solid.volume, 62.0, abs_tol=1.0e-6)


def test_document_edit_adds_reorders_and_removes_boolean_inputs():
    document = ProceduralMeshDocument()
    first = document.add_primitive_operation("box")
    second = document.add_primitive_operation("sphere")
    third = document.add_primitive_operation("cylinder")
    fourth = document.add_primitive_operation("cone")
    assert first is not None
    assert second is not None
    assert third is not None
    assert fourth is not None
    operation = document.add_boolean_operation("subtract", [first.id, second.id])
    assert operation is not None

    assert add_boolean_input(document, operation.id, third.id)
    assert operation.inputs == [first.id, second.id, third.id]
    assert not add_boolean_input(document, operation.id, third.id)

    assert move_boolean_input(document, operation.id, operation.id, third.id, 1)
    assert operation.inputs == [first.id, third.id, second.id]

    assert add_boolean_input(document, operation.id, fourth.id, 0)
    assert operation.inputs == [fourth.id, first.id, third.id, second.id]

    assert remove_boolean_input(document, operation.id, third.id)
    assert operation.inputs == [fourth.id, first.id, second.id]


def test_document_edit_rejects_boolean_input_cycles_and_invalid_removal():
    document = ProceduralMeshDocument()
    first = document.add_primitive_operation("box")
    second = document.add_primitive_operation("sphere")
    third = document.add_primitive_operation("cylinder")
    assert first is not None
    assert second is not None
    assert third is not None
    inner = document.add_boolean_operation("union", [first.id, second.id])
    outer = document.add_boolean_operation("subtract", [inner.id, third.id])
    assert inner is not None
    assert outer is not None

    assert not add_boolean_input(document, inner.id, outer.id)
    assert inner.inputs == [first.id, second.id]
    assert not remove_boolean_input(document, inner.id, first.id)
    assert inner.inputs == [first.id, second.id]


def test_csg_editor_controller_owns_selection_and_boolean_input_workflow():
    controller = CsgEditorController()

    assert controller.add_primitive("box").success
    first_id = controller.selection[1]
    assert controller.add_primitive("sphere").success
    second_id = controller.selection[1]

    boolean_result = controller.add_boolean_operation("subtract")
    assert boolean_result.success
    assert boolean_result.fit_camera
    subtract_id = controller.selection[1]
    subtract_op = controller.document.find_operation(subtract_id)
    assert subtract_op is not None
    assert subtract_op.inputs == [first_id, second_id]

    assert controller.add_primitive("cylinder").success
    third_id = controller.selection[1]
    add_input_result = controller.add_boolean_input(subtract_id, third_id)
    assert add_input_result.success
    assert controller.selection == ("operation", third_id)
    assert subtract_op.inputs == [first_id, second_id, third_id]

    move_result = controller.move_boolean_input(subtract_id, subtract_id, third_id, 1)
    assert move_result.success
    assert subtract_op.inputs == [first_id, third_id, second_id]
    assert len(evaluate_document(controller.document)) == 1


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


def test_set_path_point_updates_local_path_coordinates():
    document = ProceduralMeshDocument()
    path = document.add_path_on_plane_from_points(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
        ],
        ProceduralPlane(),
        purpose="wall",
    )
    assert path is not None

    assert set_path_point(document, path.id, 2, (2.0, 1.5))
    assert path.points[2] == (2.0, 1.5)
    assert not set_path_point(document, path.id, 99, (0.0, 0.0))
    assert not set_path_point(document, "missing", 0, (0.0, 0.0))


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


def test_csg_editor_panel_updates_extrude_vector():
    controller = CsgEditorController()
    panel = _test_editor_panel(controller)
    contour = controller.document.add_contour_from_points(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ]
    )
    assert contour is not None

    sketch_id = controller.document.find_sketch_id_for_contour(contour.id)
    operation = controller.document.add_extrude_operation_for_sketch(sketch_id, height=1.0)
    assert operation is not None

    controller.selection = ("operation", operation.id)
    panel.refresh_operation_params_panel()
    assert panel.operation_params_panel.visible is True
    assert panel.extrude_vector_inputs["z"].value == 1.0

    panel.extrude_vector_inputs["x"].value = 0.25
    panel.extrude_vector_inputs["z"].value = -2.0
    panel.operation_params._on_extrude_vector_changed(-2.0)

    assert operation.params["vector"] == [0.25, 0.0, -2.0]


def test_csg_editor_panel_updates_boolean_transform():
    controller = CsgEditorController()
    panel = _test_editor_panel(controller)
    first = controller.document.add_primitive_operation("box", {"size": [2.0, 2.0, 2.0]})
    second = controller.document.add_primitive_operation("sphere", {"radius": 0.75})
    assert first is not None
    assert second is not None
    operation = controller.document.add_boolean_operation("subtract", [first.id, second.id])
    assert operation is not None

    controller.selection = ("operation", operation.id)
    panel.refresh_operation_params_panel()
    assert panel.operation_params_panel.visible is True
    assert "center.x" in panel.operation_transform_inputs
    assert "rotation.z" in panel.operation_transform_inputs
    assert panel.extrude_vector_inputs == {}

    panel.operation_transform_inputs["center.x"].value = 3.0
    panel.operation_transform_inputs["rotation.z"].value = 45.0
    panel.operation_params._on_operation_transform_changed(3.0)

    assert operation.params["center"] == [3.0, 0.0, 0.0]
    assert operation.params["rotation"] == [0.0, 0.0, 45.0]


def test_cad_app_tree_drop_adds_and_reorders_boolean_inputs():
    from termin.csg.cad_app import CadApp

    app = CadApp()
    first = app.document.add_primitive_operation("box")
    second = app.document.add_primitive_operation("sphere")
    assert first is not None
    assert second is not None
    operation = app.document.add_boolean_operation("subtract", [first.id, second.id])
    assert operation is not None
    third = app.document.add_primitive_operation("cylinder")
    assert third is not None
    app.refresh_tree()

    subtract_node = _first_tree_node(app.tree.root_nodes, ("operation", operation.id))
    third_root_node = _first_tree_node(app.tree.root_nodes, ("operation", third.id))
    assert subtract_node is not None
    assert third_root_node is not None

    app._on_tree_drop(third_root_node, subtract_node, "inside")
    assert operation.inputs == [first.id, second.id, third.id]
    assert len(evaluate_document(app.document)) == 1

    second_node = _first_tree_node(app.tree.root_nodes, ("operation", second.id))
    third_node = _first_tree_node(app.tree.root_nodes, ("operation", third.id))
    assert second_node is not None
    assert third_node is not None

    app._on_tree_drop(third_node, second_node, "above")
    assert operation.inputs == [first.id, third.id, second.id]

    roots = build_document_tree(app.document)
    assert roots[0].children[0].text.startswith("[Base]")
    assert roots[0].children[1].text.startswith("[Cut]")
    assert roots[0].children[2].text.startswith("[Cut]")


def _first_tree_node(nodes, data):
    for node in nodes:
        if node.data == data:
            return node
        found = _first_tree_node(node.subnodes, data)
        if found is not None:
            return found
    return None


def test_csg_editor_panel_updates_sketch_plane():
    controller = CsgEditorController()
    panel = _test_editor_panel(controller)
    contour = controller.document.add_contour_from_points(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ]
    )
    assert contour is not None

    sketch_id = controller.document.find_sketch_id_for_contour(contour.id)
    controller.selection = ("plane", sketch_id)
    panel.refresh_plane_params_panel()
    assert panel.plane_params_panel.visible is True
    assert panel.plane_inputs["origin.z"].value == 0.0

    panel.plane_inputs["origin.z"].value = 2.5
    panel.plane_params._on_param_changed(2.5)

    sketch = controller.document.find_sketch(sketch_id)
    assert sketch is not None
    assert sketch.plane.origin == (0.0, 0.0, 2.5)


def test_csg_editor_panel_updates_contour_points():
    controller = CsgEditorController()
    panel = _test_editor_panel(controller)
    contour = controller.document.add_contour_from_points(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ]
    )
    assert contour is not None

    controller.selection = ("contour", contour.id)
    panel.refresh_contour_params_panel()
    assert panel.contour_params_panel.visible is True
    assert panel.contour_point_inputs[(2, "x")].value == 1.0
    assert panel.contour_point_inputs[(2, "y")].value == 1.0

    panel.contour_point_inputs[(2, "x")].value = 1.75
    panel.contour_point_inputs[(2, "y")].value = 1.25
    panel.contour_params._on_point_changed(2, "y", 1.25)

    assert contour.points[2] == (1.75, 1.25)


def test_cad_app_drags_selected_contour_point_in_viewport_without_drawing():
    from termin.csg.cad_app import CadApp

    app = CadApp()
    app.editor_panel.build_contour_params_panel()
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
    sketch = app.document.find_sketch(sketch_id)
    assert sketch is not None

    app.selected_node_data = ("contour", contour.id)
    app.editor_panel.refresh_contour_params_panel()
    app.mode = "draw_sketch"

    width = 800
    height = 600
    start_screen = app._project_world_to_screen(sketch.plane.unproject(contour.points[2]), width, height)
    target_screen = app._project_world_to_screen(sketch.plane.unproject((1.5, 1.25)), width, height)
    assert start_screen is not None
    assert target_screen is not None

    assert app._on_scene_mouse_down(start_screen[0], start_screen[1], width, height) is True
    assert app.draft.points == []
    assert app._on_scene_mouse_move(target_screen[0], target_screen[1], width, height) is True
    assert app._on_scene_mouse_up(target_screen[0], target_screen[1], width, height) is True

    assert isclose(contour.points[2][0], 1.5, abs_tol=1.0e-3)
    assert isclose(contour.points[2][1], 1.25, abs_tol=1.0e-3)
    assert isclose(app.editor_panel.contour_point_inputs[(2, "x")].value, 1.5, abs_tol=1.0e-3)
    assert isclose(app.editor_panel.contour_point_inputs[(2, "y")].value, 1.25, abs_tol=1.0e-3)
    assert app.draft.points == []


def test_cad_app_drags_selected_path_point_in_viewport_without_drawing():
    from termin.csg.cad_app import CadApp

    app = CadApp()
    path = app.document.add_path_on_plane_from_points(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
        ],
        ProceduralPlane(),
        purpose="wall",
    )
    assert path is not None
    sketch_id = app.document.find_sketch_id_for_path(path.id)
    sketch = app.document.find_sketch(sketch_id)
    assert sketch is not None
    operation = app.document.add_wall_operation_for_sketch(sketch_id, height=2.0, thickness=0.5)
    assert operation is not None

    app.selected_node_data = ("path", path.id)
    app.mode = "draw_sketch"

    width = 800
    height = 600
    start_screen = app._project_world_to_screen(sketch.plane.unproject(path.points[2]), width, height)
    target_screen = app._project_world_to_screen(sketch.plane.unproject((1.5, 1.25)), width, height)
    assert start_screen is not None
    assert target_screen is not None

    assert app._on_scene_mouse_down(start_screen[0], start_screen[1], width, height) is True
    assert app.draft.points == []
    assert app._on_scene_mouse_move(target_screen[0], target_screen[1], width, height) is True
    assert app._on_scene_mouse_up(target_screen[0], target_screen[1], width, height) is True

    assert isclose(path.points[2][0], 1.5, abs_tol=1.0e-3)
    assert isclose(path.points[2][1], 1.25, abs_tol=1.0e-3)
    evaluated = evaluate_document(app.document)
    assert len(evaluated) == 1
    assert evaluated[0].operation_id == operation.id
    assert evaluated[0].solid.volume > 1.0
    assert app.draft.points == []


def test_cad_app_draw_sketch_scene_click_uses_controller_draft_state():
    from termin.csg.cad_app import CadApp

    app = CadApp()
    app.start_draw_sketch()

    assert app._on_scene_click(400.0, 300.0, 800, 600) is True

    assert app.mode == "draw_sketch"
    assert len(app.draft.points) == 1
    assert app.preview_revision == 2


def test_cad_app_close_contour_leaves_draw_sketch_mode():
    from termin.csg.cad_app import CadApp
    from termin.csg.document_edit import start_sketch_draft

    app = CadApp()
    app.start_draw_sketch()
    app.draft = start_sketch_draft()
    app.draft.plane = ProceduralPlane()
    app.draft.points = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
    ]

    app.close_contour()

    assert app.mode == "idle"
    assert app.draft.points == []
    assert app.document.contour_count() == 1


def test_cad_app_add_wall_path_action_finishes_open_path():
    from termin.csg.cad_app import CadApp

    app = CadApp()
    contour = app.document.add_contour_from_points(
        [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
        ]
    )
    assert contour is not None

    sketch_id = app.document.find_sketch_id_for_contour(contour.id)
    app.selected_node_data = ("sketch", sketch_id)
    app.start_add_wall_path()

    assert app.mode == "draw_sketch"
    assert app.draft.sketch_id == sketch_id
    assert app.draft.purpose == "wall"

    app.draft.points = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
    ]
    app.finish_wall_path()

    assert app.mode == "idle"
    assert app.selected_node_data is not None
    assert app.selected_node_data[0] == "path"
    assert app.document.path_count() == 1
    path_ref = app.document.find_path_ref(app.selected_node_data[1])
    assert path_ref is not None
    assert path_ref[1].closed is False


def test_cad_app_wall_action_and_params_update_operation():
    from termin.csg.cad_app import CadApp

    app = CadApp()
    path = app.document.add_path_on_plane_from_points(
        [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
        ],
        ProceduralPlane(),
        purpose="wall",
    )
    assert path is not None
    sketch_id = app.document.find_sketch_id_for_path(path.id)

    app.selected_node_data = ("sketch", sketch_id)
    app.wall_selected()

    assert app.selected_node_data is not None
    assert app.selected_node_data[0] == "operation"
    operation = app.document.find_operation(app.selected_node_data[1])
    assert operation is not None
    assert operation.kind == OPERATION_KIND_WALL
    assert operation.params["source_sketch_id"] == sketch_id
    assert operation.inputs == [path.id]

    app.editor_panel.refresh_operation_params_panel()
    assert app.editor_panel.operation_params_panel.visible is True
    assert app.editor_panel.wall_param_inputs["height"].value == 3.0
    assert app.editor_panel.wall_param_inputs["thickness"].value == 0.2

    app.editor_panel.wall_param_inputs["height"].value = 2.5
    app.editor_panel.wall_param_inputs["thickness"].value = 0.4
    app.editor_panel.set_wall_alignment("left")

    assert operation.params["height"] == 2.5
    assert operation.params["thickness"] == 0.4
    assert operation.params["alignment"] == "left"
    evaluated = evaluate_document(app.document)
    assert len(evaluated) == 1
    assert isclose(evaluated[0].solid.volume, 2.0, abs_tol=1.0e-6)


def test_cad_app_add_hole_action_closes_contour_inside_selected_outer():
    from termin.csg.cad_app import CadApp

    app = CadApp()
    outer = app.document.add_contour_from_points(
        [
            (0.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
            (4.0, 4.0, 0.0),
            (0.0, 4.0, 0.0),
        ]
    )
    assert outer is not None

    sketch_id = app.document.find_sketch_id_for_contour(outer.id)
    app.selected_node_data = ("contour", outer.id)
    app.start_add_hole_contour()
    assert app.mode == "draw_sketch"
    assert app.draft.sketch_id == sketch_id
    assert app.draft.contour_role == CONTOUR_ROLE_HOLE
    assert app.draft.parent_contour_id == outer.id

    app.draft.points = [
        (1.0, 1.0, 0.0),
        (3.0, 1.0, 0.0),
        (3.0, 3.0, 0.0),
    ]
    app.close_contour()

    assert app.mode == "idle"
    assert app.selected_node_data is not None
    assert app.selected_node_data[0] == "contour"
    contour_ref = app.document.find_contour_ref(app.selected_node_data[1])
    assert contour_ref is not None
    _sketch, hole = contour_ref
    assert hole.role == CONTOUR_ROLE_HOLE
    assert hole.parent_contour_id == outer.id


def test_csg_editor_panel_updates_primitive_operation_params():
    controller = CsgEditorController()
    panel = _test_editor_panel(controller)
    panel.add_primitive("box")

    assert controller.selection is not None
    operation = controller.document.find_operation(controller.selection[1])
    assert operation is not None
    assert operation.kind == "primitive"

    panel.refresh_primitive_params_panel()
    assert panel.primitive_params_panel.visible is True
    assert panel.primitive_param_inputs["size.x"].value == 1.0

    panel.primitive_param_inputs["size.x"].value = 2.5
    panel.primitive_param_inputs["center.z"].value = 1.25
    panel.primitive_params._on_param_changed(2.5)

    assert operation.params["size"] == [2.5, 1.0, 1.0]
    assert operation.params["center"] == [0.0, 0.0, 1.25]
    evaluated = evaluate_document(controller.document)
    assert len(evaluated) == 1
    assert isclose(evaluated[0].solid.volume, 2.5, abs_tol=1.0e-6)


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
    assert len(reference.lines or []) == 43
    assert all(line.depth_test for line in reference.lines or [])
    assert (
        sum(
            1
            for line in reference.lines or []
            if line.start == (-10, 0.0, 0.0)
            and line.end == (10, 0.0, 0.0)
            and line.color == (0.92, 0.18, 0.18, 1.0)
        )
        == 1
    )
    assert (
        sum(
            1
            for line in reference.lines or []
            if line.start == (0.0, -10, 0.0)
            and line.end == (0.0, 10, 0.0)
            and line.color == (0.18, 0.82, 0.22, 1.0)
        )
        == 1
    )

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
