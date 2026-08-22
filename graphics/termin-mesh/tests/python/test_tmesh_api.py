import math
import uuid
from array import array

import numpy as np
import tmesh
import pytest
from tcbase import clear_resource_loader, set_resource_loader
from tcbase._geom_native import Ray3, Vec3


def _v3(value) -> Vec3:
    return Vec3(float(value[0]), float(value[1]), float(value[2]))


def _assert_vec3_approx(actual: Vec3, expected, abs: float = 1e-6) -> None:
    assert actual.x == pytest.approx(expected[0], abs=abs)
    assert actual.y == pytest.approx(expected[1], abs=abs)
    assert actual.z == pytest.approx(expected[2], abs=abs)


def _typed_memoryview(values: array, format_code: str, shape: tuple[int, ...]):
    return memoryview(values).cast("B").cast(format_code, shape=shape)


def test_vertex_layout_building():
    layout = tmesh.TcVertexLayout()
    ok1 = layout.add("position", 3, tmesh.TcAttribType.FLOAT32, 0)
    ok2 = layout.add("normal", 3, tmesh.TcAttribType.FLOAT32, 1)
    ok3 = layout.add("uv", 2, tmesh.TcAttribType.FLOAT32, 2)

    assert ok1 and ok2 and ok3
    assert layout.attrib_count == 3
    assert layout.stride == 32

    uv = layout.find("uv")
    assert uv is not None
    assert uv["offset"] == 24


def test_vertex_layout_can_request_shader_owned_input_locations():
    layout = tmesh.TcVertexLayout()
    assert layout.use_shader_input_locations == 0

    layout.use_shader_input_locations = 1
    assert layout.use_shader_input_locations == 1


def test_skinned_layout_matches_gpu_contract():
    layout = tmesh.TcVertexLayout.skinned()
    assert layout.attrib_count == 6
    assert layout.stride == 80

    tangent = layout.find("tangent")
    joints = layout.find("joints")
    weights = layout.find("weights")

    assert tangent is not None
    assert tangent["location"] == 3
    assert joints is not None
    assert joints["location"] == 4
    assert weights is not None
    assert weights["location"] == 5
def test_mesh3_from_numpy_arrays():
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=np.float32,
    )
    triangles = np.array([[0, 1, 2]], dtype=np.uint32)

    mesh = tmesh.Mesh3(vertices=vertices, triangles=triangles, name="tri")
    assert mesh.is_valid()
    assert mesh.vertex_count == 3
    assert mesh.triangle_count == 1
    assert mesh.name == "tri"


def test_mesh3_transforms_use_vector_geometry_internally():
    vertices = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
    mesh = tmesh.Mesh3(vertices=vertices, triangles=np.empty((0, 3), dtype=np.uint32))

    mesh.translate(2.0, -1.0, 0.5)
    mesh.scale(2.0, 3.0, 4.0)

    np.testing.assert_allclose(mesh.vertices, [[6.0, 3.0, 14.0]])


def test_mesh3_nonuniform_scale_refreshes_existing_normals():
    vertices = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 1.0], [0.0, 1.0, 1.0]],
        dtype=np.float32,
    )
    triangles = np.array([[0, 1, 2]], dtype=np.uint32)
    mesh = tmesh.Mesh3(vertices=vertices, triangles=triangles)
    mesh.compute_normals()

    mesh.scale(2.0, 1.0, 0.5)

    edges = mesh.vertices[mesh.triangles[0, 1:]] - mesh.vertices[mesh.triangles[0, 0]]
    expected = np.cross(edges[0], edges[1])
    expected /= np.linalg.norm(expected)
    np.testing.assert_allclose(mesh.vertex_normals, np.tile(expected, (3, 1)), atol=1e-6)


@pytest.mark.parametrize("meridians, parallels", [(16, 16), (3, 2), (5, 3)])
def test_uv_sphere_has_non_degenerate_outward_faces_and_finite_vertex_data(
    meridians: int,
    parallels: int,
):
    mesh = tmesh.UVSphereMesh(n_meridians=meridians, n_parallels=parallels)
    vertices = mesh.vertices
    triangles = mesh.triangles
    assert len(triangles) == 2 * meridians * (parallels - 1)
    assert np.all(np.diff(np.sort(triangles, axis=1), axis=1) != 0)

    face_points = vertices[triangles]
    face_normals = np.cross(face_points[:, 1] - face_points[:, 0], face_points[:, 2] - face_points[:, 0])
    areas_twice = np.linalg.norm(face_normals, axis=1)
    assert np.all(areas_twice > 1e-6)
    centroids = face_points.mean(axis=1)
    assert np.all(np.einsum("ij,ij->i", face_normals, centroids) > 0.0)
    assert np.isfinite(mesh.vertex_normals).all()
    assert np.isfinite(mesh.tangents).all()


def test_mesh3_from_buffer_compatible_memoryviews():
    vertices = _typed_memoryview(
        array(
            "f",
            [
                0.0, 0.0, 0.0,
                1.0, 0.0, 0.0,
                0.0, 1.0, 0.0,
            ],
        ),
        "f",
        (3, 3),
    )
    triangles = _typed_memoryview(array("I", [0, 1, 2]), "I", (1, 3))

    mesh = tmesh.Mesh3(vertices=vertices, triangles=triangles, name="buffer-tri")

    assert mesh.is_valid()
    assert mesh.vertex_count == 3
    assert mesh.triangle_count == 1
    assert mesh.name == "buffer-tri"


def test_mesh3_rejects_flat_vertex_buffer_shape():
    vertices = array(
        "f",
        [
            0.0, 0.0, 0.0,
            1.0, 0.0, 0.0,
            0.0, 1.0, 0.0,
        ],
    )
    triangles = _typed_memoryview(array("I", [0, 1, 2]), "I", (1, 3))

    with pytest.raises(TypeError):
        tmesh.Mesh3(vertices=vertices, triangles=triangles, name="flat-tri")


def test_mesh_registry_set_data_smoke():
    mesh_uuid = f"pytest-{uuid.uuid4()}"
    handle = tmesh.tc_mesh_get_or_create(mesh_uuid)
    assert handle.is_valid
    assert tmesh.tc_mesh_contains(handle.uuid)

    layout = tmesh.TcVertexLayout.pos_normal_uv()
    vertices = np.array(
        [
            0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0,
            1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0,
            0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0,
        ],
        dtype=np.float32,
    )
    indices = np.array([0, 1, 2], dtype=np.uint32)

    ok = tmesh.tc_mesh_set_data(handle, vertices, 3, layout, indices, "pytest-mesh")
    assert ok
    assert handle.vertex_count == 3
    assert handle.index_count == 3
    assert handle.submesh_count == 1
    submesh = handle.submesh_at(0)
    assert submesh is not None
    assert submesh.first_index == 0
    assert submesh.index_count == 3
    assert submesh.material_slot == 0
    assert tmesh.tc_mesh_count() >= 1

    all_info = tmesh.tc_mesh_get_all_info()
    assert any(info["uuid"] == handle.uuid for info in all_info)


def test_tc_mesh_submesh_ranges_and_material_slots():
    mesh_uuid = f"pytest-submesh-{uuid.uuid4()}"
    layout = tmesh.TcVertexLayout.pos_normal_uv()
    vertices = np.array(
        [
            0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0,
            1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0,
            0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0,
            2.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0,
            3.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0,
            2.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0,
        ],
        dtype=np.float32,
    )
    indices = np.array([0, 1, 2, 3, 4, 5], dtype=np.uint32)
    submeshes = [
        tmesh.TcSubmesh(first_index=0, index_count=3, material_slot=0, name="left"),
        tmesh.TcSubmesh(first_index=3, index_count=3, material_slot=1, name="right"),
    ]

    handle = tmesh.TcMesh.from_interleaved_with_submeshes(
        vertices,
        6,
        indices,
        layout,
        submeshes,
        "pytest-submesh-mesh",
        mesh_uuid,
    )

    assert handle.is_valid
    assert handle.submesh_count == 2
    left = handle.submesh_at(0)
    right = handle.submesh_at(1)
    assert left is not None
    assert right is not None
    assert left.first_index == 0
    assert left.index_count == 3
    assert left.material_slot == 0
    assert left.name == "left"
    assert right.first_index == 3
    assert right.index_count == 3
    assert right.material_slot == 1
    assert right.name == "right"


def _cube_tc_mesh():
    h = 1.5
    z0 = 0.5
    z1 = 3.5
    vertices = np.array(
        [
            [-h, -h, z0],
            [h, -h, z0],
            [h, h, z0],
            [-h, h, z0],
            [-h, -h, z1],
            [h, -h, z1],
            [h, h, z1],
            [-h, h, z1],
        ],
        dtype=np.float32,
    )
    triangles = np.array(
        [
            [4, 5, 6],
            [4, 6, 7],
            [0, 2, 1],
            [0, 3, 2],
            [1, 2, 6],
            [1, 6, 5],
            [3, 7, 6],
            [3, 6, 2],
            [0, 4, 7],
            [0, 7, 3],
            [0, 1, 5],
            [0, 5, 4],
        ],
        dtype=np.uint32,
    )
    mesh = tmesh.Mesh3(vertices=vertices, triangles=triangles, name="surface-edge-cube")
    return tmesh.TcMesh.from_mesh3(mesh, f"surface-edge-cube-{uuid.uuid4()}")


def _triangle_tc_mesh():
    mesh = tmesh.Mesh3(
        vertices=np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
            ],
            dtype=np.float32,
        ),
        triangles=np.array([[0, 1, 2]], dtype=np.uint32),
        name="raycast-triangle",
    )
    return tmesh.TcMesh.from_mesh3(mesh, f"raycast-triangle-{uuid.uuid4()}")


def _raw_ray(origin: Vec3, direction: Vec3) -> Ray3:
    ray = Ray3()
    ray.origin = origin
    ray.direction = direction
    return ray


def test_tc_mesh_raycast_returns_typed_rich_hit_and_public_export():
    from termin.mesh import TcMeshRayHit as PublicTcMeshRayHit

    mesh = _triangle_tc_mesh()
    hit = mesh.raycast(Ray3(Vec3(0.25, 0.25, 1.0), Vec3.down()))

    assert hit is not None
    assert isinstance(hit, tmesh.TcMeshRayHit)
    assert PublicTcMeshRayHit is tmesh.TcMeshRayHit
    assert isinstance(hit.distance, float)
    assert isinstance(hit.position, Vec3)
    assert isinstance(hit.normal, Vec3)
    assert isinstance(hit.barycentric, Vec3)
    assert hit.distance == pytest.approx(1.0)
    _assert_vec3_approx(hit.position, (0.25, 0.25, 0.0))
    _assert_vec3_approx(hit.normal, (0.0, 0.0, 1.0))
    _assert_vec3_approx(hit.barycentric, (0.5, 0.25, 0.25))
    assert hit.triangle_index == 0
    assert hit.indices == (0, 1, 2)
    assert isinstance(hit.indices, tuple)

    with pytest.raises(AttributeError):
        hit.distance = 2.0
    with pytest.raises(AttributeError):
        hit.position = Vec3.zero()
    with pytest.raises(AttributeError):
        hit.indices = (2, 1, 0)


@pytest.mark.parametrize("direction_scale", [0.25, 4.0, 1.0e300])
def test_tc_mesh_raycast_distance_is_metric_for_non_unit_ray(direction_scale: float):
    mesh = _triangle_tc_mesh()
    origin = Vec3(0.25, 0.25, 1.0)
    ray = _raw_ray(origin, Vec3(0.0, 0.0, -direction_scale))

    hit = mesh.raycast(ray)

    assert hit is not None
    assert hit.distance == pytest.approx(1.0)
    normalized_direction = ray.direction.try_normalized()
    assert normalized_direction is not None
    _assert_vec3_approx(hit.position, origin + normalized_direction * hit.distance)


def test_tc_mesh_raycast_uses_a_closed_signed_metric_range():
    mesh = _triangle_tc_mesh()
    forward_ray = Ray3(Vec3(0.25, 0.25, 1.0), Vec3.down())

    boundary_hit = mesh.raycast(forward_ray, min_distance=1.0, max_distance=1.0)
    assert boundary_hit is not None
    assert boundary_hit.distance == pytest.approx(1.0)
    assert mesh.raycast(forward_ray, min_distance=0.0, max_distance=0.999) is None

    backward_hit = mesh.raycast(
        Ray3(Vec3(0.25, 0.25, -1.0), Vec3.down()),
        min_distance=-1.0,
        max_distance=-1.0,
    )
    assert backward_hit is not None
    assert backward_hit.distance == pytest.approx(-1.0)
    _assert_vec3_approx(backward_hit.position, (0.25, 0.25, 0.0))


def test_tc_mesh_raycast_float_boundary_never_expands_the_requested_range():
    mesh = _triangle_tc_mesh()
    ray = Ray3(Vec3(0.25, 0.25, 1.0), Vec3.down())
    below_hit = math.nextafter(1.0, -math.inf)
    above_hit = math.nextafter(1.0, math.inf)

    assert mesh.raycast(ray, min_distance=below_hit, max_distance=below_hit) is None
    assert mesh.raycast(ray, min_distance=above_hit, max_distance=above_hit) is None
    assert mesh.raycast(ray, min_distance=below_hit, max_distance=1.0) is not None
    assert mesh.raycast(ray, min_distance=1.0, max_distance=above_hit) is not None


def test_tc_mesh_raycast_reports_miss_and_rejects_old_flat_signature():
    mesh = _triangle_tc_mesh()

    assert mesh.raycast(Ray3(Vec3(2.0, 2.0, 1.0), Vec3.down())) is None
    with pytest.raises(TypeError):
        mesh.raycast((0.25, 0.25, 1.0), (0.0, 0.0, -1.0))


@pytest.mark.parametrize(
    "origin",
    [
        Vec3(math.nan, 0.25, 1.0),
        Vec3(math.inf, 0.25, 1.0),
        Vec3(1.0e300, 0.25, 1.0),
        Vec3(math.ulp(0.0), 0.25, 1.0),
    ],
)
def test_tc_mesh_raycast_rejects_invalid_or_unrepresentable_origin(origin: Vec3):
    mesh = _triangle_tc_mesh()

    assert mesh.raycast(_raw_ray(origin, Vec3.down())) is None


@pytest.mark.parametrize(
    "direction",
    [
        Vec3.zero(),
        Vec3(math.nan, 0.0, -1.0),
        Vec3(math.inf, 0.0, -1.0),
    ],
)
def test_tc_mesh_raycast_rejects_invalid_or_degenerate_direction(direction: Vec3):
    mesh = _triangle_tc_mesh()

    assert mesh.raycast(_raw_ray(Vec3(0.25, 0.25, 1.0), direction)) is None


@pytest.mark.parametrize(
    "min_distance,max_distance",
    [
        (math.nan, 2.0),
        (0.0, math.inf),
        (2.0, 1.0),
        (-1.0e300, 2.0),
        (0.0, 1.0e300),
    ],
)
def test_tc_mesh_raycast_rejects_invalid_or_unrepresentable_range(
    min_distance: float,
    max_distance: float,
):
    mesh = _triangle_tc_mesh()

    assert (
        mesh.raycast(
            Ray3(Vec3(0.25, 0.25, 1.0), Vec3.down()),
            min_distance=min_distance,
            max_distance=max_distance,
        )
        is None
    )


def _cube_tc_mesh_with_unshared_triangle_vertices():
    shared = _cube_tc_mesh()
    vertices = shared.vertices
    triangles = shared.triangles
    expanded_vertices = []
    expanded_triangles = []
    for tri in triangles:
        base = len(expanded_vertices)
        expanded_vertices.extend([
            vertices[int(tri[0])],
            vertices[int(tri[1])],
            vertices[int(tri[2])],
        ])
        expanded_triangles.append([base, base + 1, base + 2])

    mesh = tmesh.Mesh3(
        vertices=np.asarray(expanded_vertices, dtype=np.float32),
        triangles=np.asarray(expanded_triangles, dtype=np.uint32),
        name="surface-edge-cube-unshared",
    )
    return tmesh.TcMesh.from_mesh3(mesh, f"surface-edge-cube-unshared-{uuid.uuid4()}")


def _box_tc_mesh_unshared(width: float, depth: float, height: float):
    x0 = -width * 0.5
    x1 = width * 0.5
    y0 = -depth * 0.5
    y1 = depth * 0.5
    z0 = 0.5
    z1 = z0 + height

    faces = [
        ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),
        ((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)),
        ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),
        ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)),
        ((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)),
        ((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)),
    ]

    vertices = []
    triangles = []
    for quad in faces:
        base = len(vertices)
        vertices.extend([quad[0], quad[1], quad[2], quad[0], quad[2], quad[3]])
        triangles.append([base, base + 1, base + 2])
        triangles.append([base + 3, base + 4, base + 5])

    mesh = tmesh.Mesh3(
        vertices=np.asarray(vertices, dtype=np.float32),
        triangles=np.asarray(triangles, dtype=np.uint32),
        name="surface-edge-wall-box-unshared",
    )
    return tmesh.TcMesh.from_mesh3(mesh, f"surface-edge-wall-box-unshared-{uuid.uuid4()}")


def test_surface_edge_queries_return_typed_read_only_hits_and_public_export():
    from termin.mesh import TcMeshSurfaceEdgeHit as PublicTcMeshSurfaceEdgeHit

    mesh = _cube_tc_mesh()
    point = Vec3(1.3, 0.0, 3.5)
    normal = Vec3.up()
    hits = (
        mesh.find_surface_edge(start_triangle=0, point=point, normal=normal),
        mesh.find_surface_edge_aligned(
            start_triangle=0,
            point=point,
            normal=normal,
            edge_direction=Vec3.unit_y(),
            max_angle_degrees=0.0,
        ),
        mesh.find_nearest_surface_edge(point=point),
    )

    assert PublicTcMeshSurfaceEdgeHit is tmesh.TcMeshSurfaceEdgeHit
    for hit in hits:
        assert hit is not None
        assert type(hit) is tmesh.TcMeshSurfaceEdgeHit
        assert isinstance(hit.point, Vec3)
        assert isinstance(hit.indices, tuple)
        assert len(hit.indices) == 2
        assert all(isinstance(index, int) for index in hit.indices)
        assert isinstance(hit.distance, float)
        assert isinstance(hit.side, int)

    hit = hits[0]
    assert hit is not None
    _assert_vec3_approx(hit.point, (1.5, 0.0, 3.5))
    assert hit.distance == pytest.approx(0.2, abs=1e-6)

    with pytest.raises(AttributeError):
        hit.point = Vec3.zero()
    with pytest.raises(AttributeError):
        hit.indices = (0, 1)
    with pytest.raises(AttributeError):
        hit.distance = 1.0
    with pytest.raises(AttributeError):
        hit.side = 0
    with pytest.raises(TypeError):
        hit["point"]


@pytest.mark.parametrize("direction_magnitude", [1.0e-300, 1.0e300])
def test_surface_edge_query_direction_magnitude_is_ignored(direction_magnitude: float):
    mesh = _cube_tc_mesh()
    point = Vec3(1.3, 0.0, 3.5)
    scaled_up = Vec3(0.0, 0.0, direction_magnitude)

    surface_hit = mesh.find_surface_edge(
        start_triangle=0,
        point=point,
        normal=Vec3(0.0, 0.0, direction_magnitude),
        up=scaled_up,
    )
    aligned_hit = mesh.find_surface_edge_aligned(
        start_triangle=0,
        point=point,
        normal=Vec3(0.0, 0.0, direction_magnitude),
        edge_direction=Vec3(0.0, direction_magnitude, 0.0),
        max_angle_degrees=0.0,
        up=scaled_up,
    )
    nearest_hit = mesh.find_nearest_surface_edge(point=point, up=scaled_up)

    for hit in (surface_hit, aligned_hit, nearest_hit):
        assert hit is not None
        _assert_vec3_approx(hit.point, (1.5, 0.0, 3.5))
        assert hit.distance == pytest.approx(0.2, abs=1e-6)


@pytest.mark.parametrize(
    "point",
    [
        Vec3(math.nan, 0.0, 3.5),
        Vec3(math.inf, 0.0, 3.5),
        Vec3(1.0e300, 0.0, 3.5),
        Vec3(math.ulp(0.0), 0.0, 3.5),
    ],
)
def test_surface_edge_queries_reject_invalid_or_unrepresentable_points(point: Vec3):
    mesh = _cube_tc_mesh()

    assert (
        mesh.find_surface_edge(
            start_triangle=0,
            point=point,
            normal=Vec3.up(),
        )
        is None
    )
    assert mesh.find_nearest_surface_edge(point=point) is None


@pytest.mark.parametrize(
    "direction",
    [
        Vec3.zero(),
        Vec3(math.nan, 0.0, 1.0),
        Vec3(math.inf, 0.0, 1.0),
    ],
)
def test_surface_edge_queries_reject_invalid_direction_like_inputs(direction: Vec3):
    mesh = _cube_tc_mesh()
    point = Vec3(1.3, 0.0, 3.5)

    assert (
        mesh.find_surface_edge(
            start_triangle=0,
            point=point,
            normal=direction,
        )
        is None
    )
    assert (
        mesh.find_surface_edge(
            start_triangle=0,
            point=point,
            normal=Vec3.up(),
            up=direction,
        )
        is None
    )
    assert (
        mesh.find_surface_edge_aligned(
            start_triangle=0,
            point=point,
            normal=Vec3.up(),
            edge_direction=direction,
            max_angle_degrees=10.0,
        )
        is None
    )
    assert mesh.find_nearest_surface_edge(point=point, up=direction) is None


@pytest.mark.parametrize(
    "metric",
    [
        Vec3.zero(),
        Vec3(-1.0, 1.0, 1.0),
        Vec3(math.nan, 1.0, 1.0),
        Vec3(math.inf, 1.0, 1.0),
        Vec3(1.0e300, 1.0, 1.0),
        Vec3(1.0e-9, 1.0, 1.0),
        Vec3(math.ulp(0.0), 1.0, 1.0),
    ],
)
def test_surface_edge_queries_reject_invalid_or_unrepresentable_metric(metric: Vec3):
    mesh = _cube_tc_mesh()

    assert (
        mesh.find_surface_edge(
            start_triangle=0,
            point=Vec3(1.3, 0.0, 3.5),
            normal=Vec3.up(),
            metric=metric,
        )
        is None
    )


@pytest.mark.parametrize(
    "point,metric",
    [
        (
            Vec3(float(np.finfo(np.float32).max), 0.0, 3.5),
            Vec3(2.0, 1.0, 1.0),
        ),
        (
            Vec3(
                float(np.nextafter(np.float32(0.0), np.float32(1.0))),
                0.0,
                3.5,
            ),
            Vec3(1.0e-8, 1.0, 1.0),
        ),
    ],
)
def test_surface_edge_queries_reject_packed_metric_product_overflow_or_underflow(
    point: Vec3,
    metric: Vec3,
):
    mesh = _cube_tc_mesh()

    assert (
        mesh.find_surface_edge(
            start_triangle=0,
            point=point,
            normal=Vec3.up(),
            metric=metric,
        )
        is None
    )


@pytest.mark.parametrize(
    "max_angle_degrees",
    [
        math.nan,
        math.inf,
        -math.inf,
        -0.001,
        -math.ulp(0.0),
        math.nextafter(90.0, math.inf),
        90.001,
    ],
)
def test_surface_edge_aligned_query_rejects_invalid_angle(max_angle_degrees: float):
    mesh = _cube_tc_mesh()

    assert (
        mesh.find_surface_edge_aligned(
            start_triangle=0,
            point=Vec3(1.3, 0.0, 3.5),
            normal=Vec3.up(),
            edge_direction=Vec3.unit_y(),
            max_angle_degrees=max_angle_degrees,
        )
        is None
    )


def test_surface_edge_queries_reject_invalid_handle_and_start_triangle():
    assert tmesh.TcMesh().find_nearest_surface_edge(point=Vec3.zero()) is None

    mesh = _cube_tc_mesh()
    invalid_triangle = mesh.triangle_count
    assert (
        mesh.find_surface_edge(
            start_triangle=invalid_triangle,
            point=Vec3(1.3, 0.0, 3.5),
            normal=Vec3.up(),
        )
        is None
    )
    assert (
        mesh.find_surface_edge_aligned(
            start_triangle=invalid_triangle,
            point=Vec3(1.3, 0.0, 3.5),
            normal=Vec3.up(),
            edge_direction=Vec3.unit_y(),
            max_angle_degrees=10.0,
        )
        is None
    )


def test_surface_edge_query_loads_declared_mesh_before_validating_start_triangle():
    mesh_uuid = f"surface-edge-lazy-{uuid.uuid4()}"
    declared = tmesh.tc_mesh_declare(mesh_uuid, "surface-edge-lazy")
    layout = tmesh.TcVertexLayout.pos_normal_uv()
    vertices = np.array(
        [
            0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0,
            1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0,
            0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0,
        ],
        dtype=np.float32,
    )
    indices = np.array([0, 1, 2], dtype=np.uint32)

    def load_mesh(resource_uuid: str) -> bool:
        assert resource_uuid == mesh_uuid
        return tmesh.tc_mesh_set_data(
            declared,
            vertices,
            3,
            layout,
            indices,
            "surface-edge-lazy",
        )

    assert not tmesh.tc_mesh_is_loaded(declared)
    set_resource_loader(load_mesh)
    try:
        hit = declared.find_surface_edge(
            start_triangle=0,
            point=Vec3(0.2, 0.2, 0.0),
            normal=Vec3.up(),
        )
    finally:
        clear_resource_loader()

    assert tmesh.tc_mesh_is_loaded(declared)
    assert hit is not None
    _assert_vec3_approx(hit.point, (0.2, 0.0, 0.0))


@pytest.mark.parametrize(
    "point,expected_edge",
    [
        ((1.3, -1.0, 3.5), (1.5, -1.0, 3.5)),
        ((1.3, 0.0, 3.5), (1.5, 0.0, 3.5)),
        ((1.3, 1.0, 3.5), (1.5, 1.0, 3.5)),
        ((-1.3, -1.0, 3.5), (-1.5, -1.0, 3.5)),
        ((-1.3, 0.0, 3.5), (-1.5, 0.0, 3.5)),
        ((-1.3, 1.0, 3.5), (-1.5, 1.0, 3.5)),
        ((-1.0, 1.3, 3.5), (-1.0, 1.5, 3.5)),
        ((0.0, 1.3, 3.5), (0.0, 1.5, 3.5)),
        ((1.0, 1.3, 3.5), (1.0, 1.5, 3.5)),
        ((-1.0, -1.3, 3.5), (-1.0, -1.5, 3.5)),
        ((0.0, -1.3, 3.5), (0.0, -1.5, 3.5)),
        ((1.0, -1.3, 3.5), (1.0, -1.5, 3.5)),
    ],
)
def test_surface_edge_query_finds_symmetric_top_cube_edges(point, expected_edge):
    mesh = _cube_tc_mesh()

    edge = mesh.find_surface_edge(
        start_triangle=0,
        point=_v3(point),
        normal=Vec3(0.0, 0.0, 1.0),
    )

    assert edge is not None
    _assert_vec3_approx(edge.point, expected_edge)
    assert edge.distance == pytest.approx(0.2, abs=1e-6)


def test_surface_edge_query_ignores_unshared_internal_diagonal():
    mesh = _cube_tc_mesh_with_unshared_triangle_vertices()

    edge = mesh.find_surface_edge(
        start_triangle=0,
        point=Vec3(0.1, 0.0, 3.5),
        normal=Vec3(0.0, 0.0, 1.0),
    )

    assert edge is not None
    _assert_vec3_approx(edge.point, (1.5, 0.0, 3.5))
    assert edge.distance == pytest.approx(1.4, abs=1e-6)


def test_surface_edge_query_finds_nearest_edge_on_vertical_surface():
    mesh = _cube_tc_mesh()

    edge = mesh.find_surface_edge(
        start_triangle=4,
        point=Vec3(1.5, 0.0, 2.5),
        normal=Vec3(1.0, 0.0, 0.0),
    )

    assert edge is not None
    _assert_vec3_approx(edge.point, (1.5, 0.0, 3.5))
    assert edge.distance == pytest.approx(1.0, abs=1e-6)


def test_surface_edge_query_finds_short_edge_on_long_box_top_face():
    mesh = _box_tc_mesh_unshared(width=20.0, depth=1.0, height=3.0)

    edge = mesh.find_surface_edge(
        start_triangle=0,
        point=Vec3(-9.8, 0.0, 3.5),
        normal=Vec3(0.0, 0.0, 1.0),
    )

    assert edge is not None
    _assert_vec3_approx(edge.point, (-10.0, 0.0, 3.5))
    assert edge.distance == pytest.approx(0.2, abs=1e-6)


def test_surface_edge_query_uses_metric_for_distance():
    mesh = _cube_tc_mesh()

    edge = mesh.find_surface_edge(
        start_triangle=0,
        point=Vec3(0.9, 1.3, 3.5),
        normal=Vec3(0.0, 0.0, 1.0),
        metric=Vec3(0.1, 1.0, 1.0),
    )

    assert edge is not None
    _assert_vec3_approx(edge.point, (1.5, 1.3, 3.5))
    assert edge.distance == pytest.approx(0.06, abs=1e-6)


def test_surface_edge_queries_preserve_tilted_coplanar_connectivity_with_anisotropic_metric():
    mesh_data = tmesh.Mesh3(
        vertices=np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, -1.0, 0.0],
                [1.0, -1.0, 1.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float32,
        ),
        triangles=np.array([[0, 1, 2], [0, 2, 3]], dtype=np.uint32),
        name="surface-edge-tilted-quad",
    )
    mesh = tmesh.TcMesh.from_mesh3(
        mesh_data,
        f"surface-edge-tilted-quad-{uuid.uuid4()}",
    )
    point = Vec3(0.6, -0.6, 0.5)
    metric = Vec3(100.0, 1.0, 1.0)

    hits = (
        mesh.find_surface_edge(
            start_triangle=0,
            point=point,
            normal=Vec3(-1.0, -1.0, 0.0),
            up=Vec3.unit_z(),
            metric=metric,
        ),
        mesh.find_nearest_surface_edge(
            point=point,
            up=Vec3.unit_z(),
            metric=metric,
        ),
    )

    for hit in hits:
        assert hit is not None
        assert hit.indices == (0, 1)
        _assert_vec3_approx(hit.point, (0.6, -0.6, 0.0), abs=1e-5)
        assert hit.distance == pytest.approx(0.5, abs=1e-5)


def test_surface_edge_aligned_query_uses_metric_for_direction_filter():
    mesh = _cube_tc_mesh()

    edge = mesh.find_surface_edge_aligned(
        start_triangle=0,
        point=Vec3(0.9, 1.3, 3.5),
        normal=Vec3(0.0, 0.0, 1.0),
        edge_direction=Vec3(0.0, 1.0, 0.0),
        max_angle_degrees=10.0,
        metric=Vec3(0.1, 1.0, 1.0),
    )

    assert edge is not None
    _assert_vec3_approx(edge.point, (1.5, 1.3, 3.5))
    assert edge.distance == pytest.approx(0.06, abs=1e-6)


def test_surface_edge_query_finds_short_vertical_edge_on_long_box_wall_face():
    mesh = _box_tc_mesh_unshared(width=20.0, depth=1.0, height=3.0)

    edge = mesh.find_surface_edge(
        start_triangle=4,
        point=Vec3(-9.8, -0.5, 2.0),
        normal=Vec3(0.0, -1.0, 0.0),
    )

    assert edge is not None
    _assert_vec3_approx(edge.point, (-10.0, -0.5, 2.0))
    assert edge.distance == pytest.approx(0.2, abs=1e-6)
    assert edge.side == -1


def test_surface_edge_query_prefers_near_horizontal_edge_over_far_wall_end():
    mesh = _box_tc_mesh_unshared(width=20.0, depth=1.0, height=3.0)

    edge = mesh.find_surface_edge(
        start_triangle=4,
        point=Vec3(-5.0, -0.5, 3.3),
        normal=Vec3(0.0, -1.0, 0.0),
    )

    assert edge is not None
    _assert_vec3_approx(edge.point, (-5.0, -0.5, 3.5))
    assert edge.distance == pytest.approx(0.2, abs=1e-6)


def test_surface_edge_aligned_query_filters_by_vertical_edge_direction():
    mesh = _box_tc_mesh_unshared(width=20.0, depth=1.0, height=3.0)

    edge = mesh.find_surface_edge_aligned(
        start_triangle=4,
        point=Vec3(-5.0, -0.5, 3.3),
        normal=Vec3(0.0, -1.0, 0.0),
        edge_direction=Vec3(0.0, 0.0, 1.0),
        max_angle_degrees=10.0,
    )

    assert edge is not None
    _assert_vec3_approx(edge.point, (-10.0, -0.5, 3.3))
    assert edge.distance == pytest.approx(5.0, abs=1e-6)
    assert edge.side == -1


def test_surface_edge_aligned_query_rejects_mismatching_edge_direction():
    mesh = _box_tc_mesh_unshared(width=20.0, depth=1.0, height=3.0)

    edge = mesh.find_surface_edge_aligned(
        start_triangle=4,
        point=Vec3(-5.0, -0.5, 3.3),
        normal=Vec3(0.0, -1.0, 0.0),
        edge_direction=Vec3(0.0, 1.0, 0.0),
        max_angle_degrees=10.0,
    )

    assert edge is None


def test_nearest_surface_edge_query_does_not_require_start_triangle():
    mesh = _box_tc_mesh_unshared(width=20.0, depth=1.0, height=3.0)

    edge = mesh.find_nearest_surface_edge(point=Vec3(-9.8, 0.0, 3.5))

    assert edge is not None
    _assert_vec3_approx(edge.point, (-10.0, 0.0, 3.5))
    assert edge.distance == pytest.approx(0.2, abs=1e-6)
