# termin/loaders/fbx_loader.py
"""FBX loader using ufbx library."""

import numpy as np
import ufbx


class FBXMeshData:
    def __init__(self, name, vertices, normals, uvs, indices, material_index):
        self.name = name
        self.vertices = vertices
        self.normals = normals
        self.uvs = uvs
        self.indices = indices
        self.material_index = material_index


class FBXMaterialData:
    def __init__(self, name, diffuse_color=None, diffuse_texture=None):
        self.name = name
        self.diffuse_color = diffuse_color
        self.diffuse_texture = diffuse_texture


class FBXNodeData:
    def __init__(self, name, children=None, mesh_indices=None, transform=None):
        self.name = name
        self.children = children or []
        self.mesh_indices = mesh_indices or []
        self.transform = transform


class FBXAnimationChannel:
    def __init__(self, node_name, pos_keys, rot_keys, scale_keys):
        self.node_name = node_name
        self.pos_keys = pos_keys
        self.rot_keys = rot_keys
        self.scale_keys = scale_keys


class FBXAnimationClip:
    def __init__(self, name, duration, tps, channels):
        self.name = name
        self.duration = duration
        self.ticks_per_second = tps
        self.channels = channels


class FBXSceneData:
    def __init__(self):
        self.meshes = []
        self.materials = []
        self.root = None
        self.animations = []


# ---------- PARSER HELPERS ----------

def _parse_materials(scene, out):
    for mat in scene.materials:
        name = mat.name if mat.name else "Material"

        diffuse_color = None
        if mat.pbr.base_color.has_value:
            c = mat.pbr.base_color.value_vec4
            diffuse_color = np.array([c.x, c.y, c.z, c.w], dtype=np.float32)

        diffuse_texture = None
        if mat.pbr.base_color.texture:
            tex = mat.pbr.base_color.texture
            if tex.filename:
                diffuse_texture = tex.filename

        out.materials.append(
            FBXMaterialData(
                name=name,
                diffuse_color=diffuse_color,
                diffuse_texture=diffuse_texture
            )
        )


def _triangulate_face(vertex_indices, face):
    """Fan triangulation of a face with N vertices."""
    triangles = []
    begin = face.index_begin
    n = face.num_indices
    if n < 3:
        return triangles
    # Fan: (0, 1, 2), (0, 2, 3), (0, 3, 4), ...
    v0 = vertex_indices[begin]
    for i in range(1, n - 1):
        v1 = vertex_indices[begin + i]
        v2 = vertex_indices[begin + i + 1]
        triangles.append((v0, v1, v2))
    return triangles


def _parse_meshes(scene, out):
    for mesh in scene.meshes:
        if mesh.num_vertices == 0:
            continue

        # Triangulate all faces
        tri_indices = []
        for face_idx in range(mesh.num_faces):
            face = mesh.faces[face_idx]
            tri_indices.extend(_triangulate_face(mesh.vertex_indices, face))

        if not tri_indices:
            continue

        # Build vertex arrays from triangulated indices
        vertices = []
        normals = []
        uvs = []

        has_normals = mesh.vertex_normal.values and len(mesh.vertex_normal.values) > 0
        has_uvs = mesh.uv_sets and len(mesh.uv_sets) > 0 and mesh.uv_sets[0].vertex_uv.values and len(mesh.uv_sets[0].vertex_uv.values) > 0

        for v0, v1, v2 in tri_indices:
            for idx in (v0, v1, v2):
                # Position
                v = mesh.vertices[idx]
                vertices.append((v.x, v.y, v.z))

                # Normal
                if has_normals:
                    n_idx = mesh.vertex_normal.indices[idx]
                    n = mesh.vertex_normal.values[n_idx]
                    normals.append((n.x, n.y, n.z))

                # UV
                if has_uvs:
                    vertex_uv = mesh.uv_sets[0].vertex_uv
                    uv_idx = vertex_uv.indices[idx]
                    uv = vertex_uv.values[uv_idx]
                    uvs.append((uv.x, uv.y))

        vertices_np = np.array(vertices, dtype=np.float32)
        normals_np = np.array(normals, dtype=np.float32) if normals else None
        uvs_np = np.array(uvs, dtype=np.float32) if uvs else None
        indices_np = np.arange(len(vertices), dtype=np.uint32)

        # Material index
        mat_idx = 0
        if mesh.materials and len(mesh.materials) > 0:
            first_mat = mesh.materials[0]
            for i in range(len(scene.materials)):
                if scene.materials[i] == first_mat:
                    mat_idx = i
                    break

        out.meshes.append(
            FBXMeshData(
                name=mesh.name if mesh.name else "Mesh",
                vertices=vertices_np,
                normals=normals_np,
                uvs=uvs_np,
                indices=indices_np,
                material_index=mat_idx
            )
        )


def _parse_nodes_flat(scene, mesh_index_map):
    """
    Parse node hierarchy into flat list to avoid ufbx segfault issues.
    Returns root FBXNodeData with all mesh nodes as direct children.
    """
    root = FBXNodeData("Root", children=[], mesh_indices=[], transform=np.eye(4, dtype=np.float32))

    # Iterate through all nodes and collect those with meshes
    stack = [scene.root_node]
    while stack:
        node = stack.pop()

        if node.mesh:
            idx = mesh_index_map.get(id(node.mesh))
            if idx is not None:
                # Extract transform data immediately (avoid keeping ufbx refs)
                t = node.local_transform
                translation = np.array([t.translation.x, t.translation.y, t.translation.z], dtype=np.float32)
                rotation = np.array([t.rotation.x, t.rotation.y, t.rotation.z, t.rotation.w], dtype=np.float32)
                scale_vec = np.array([t.scale.x, t.scale.y, t.scale.z], dtype=np.float32)

                # Build transform matrix
                x, y, z, w = rotation
                xx, yy, zz = x * x, y * y, z * z
                xy, xz, yz = x * y, x * z, y * z
                wx, wy, wz = w * x, w * y, w * z

                rot = np.array([
                    [1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy)],
                    [2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx)],
                    [2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy)],
                ], dtype=np.float32)

                rot_scaled = rot * scale_vec

                transform = np.eye(4, dtype=np.float32)
                transform[:3, :3] = rot_scaled
                transform[:3, 3] = translation

                name = node.name if node.name else f"Mesh_{idx}"
                child = FBXNodeData(name, children=[], mesh_indices=[idx], transform=transform)
                root.children.append(child)

        # Add children to stack
        for i in range(len(node.children)):
            stack.append(node.children[i])

    return root


def _parse_animations(scene, out):
    for anim_stack in scene.anim_stacks:
        name = anim_stack.name if anim_stack.name else "Anim"

        # Get duration from layers
        duration = 0.0
        tps = 30.0  # Default ticks per second

        if anim_stack.layers:
            layer = anim_stack.layers[0]
            for anim_value in layer.anim_values:
                for curve in [anim_value.curves_x, anim_value.curves_y, anim_value.curves_z]:
                    if curve and curve.keyframes:
                        last_time = curve.keyframes[-1].time
                        if last_time > duration:
                            duration = last_time

        # Parse channels
        channels = []
        if anim_stack.layers:
            layer = anim_stack.layers[0]
            node_channels = {}

            for anim_prop in layer.anim_props:
                node = anim_prop.element
                if not node or not hasattr(node, 'name'):
                    continue

                node_name = node.name
                if node_name not in node_channels:
                    node_channels[node_name] = {
                        'pos_keys': [],
                        'rot_keys': [],
                        'scale_keys': []
                    }

                # Determine property type and extract keys
                prop_name = anim_prop.prop_name if hasattr(anim_prop, 'prop_name') else ""
                anim_value = anim_prop.anim_value

                if anim_value:
                    keys = _extract_keys(anim_value)
                    if 'translation' in prop_name.lower() or 'lcl translation' in prop_name.lower():
                        node_channels[node_name]['pos_keys'] = keys
                    elif 'rotation' in prop_name.lower() or 'lcl rotation' in prop_name.lower():
                        node_channels[node_name]['rot_keys'] = keys
                    elif 'scaling' in prop_name.lower() or 'lcl scaling' in prop_name.lower():
                        node_channels[node_name]['scale_keys'] = keys

            for node_name, ch_data in node_channels.items():
                channels.append(
                    FBXAnimationChannel(
                        node_name=node_name,
                        pos_keys=ch_data['pos_keys'],
                        rot_keys=ch_data['rot_keys'],
                        scale_keys=ch_data['scale_keys']
                    )
                )

        out.animations.append(
            FBXAnimationClip(
                name=name,
                duration=duration,
                tps=tps,
                channels=channels
            )
        )


def _extract_keys(anim_value):
    """Extract keyframes from anim value."""
    keys = []
    curves = [anim_value.curves_x, anim_value.curves_y, anim_value.curves_z]

    # Find all unique times
    times = set()
    for curve in curves:
        if curve:
            for kf in curve.keyframes:
                times.add(kf.time)

    for t in sorted(times):
        values = []
        for curve in curves:
            if curve:
                # Find value at time t (simple linear search)
                val = curve.keyframes[0].value if curve.keyframes else 0.0
                for kf in curve.keyframes:
                    if kf.time <= t:
                        val = kf.value
                values.append(val)
            else:
                values.append(0.0)
        keys.append((t, np.array(values, dtype=np.float32)))

    return keys


# ---------- PUBLIC API ----------

def load_fbx_file(path) -> FBXSceneData:
    """Load FBX file using ufbx.

    Note: ufbx has issues with multiple iterations over collections.
    All data must be extracted in a single pass.
    """
    scene_data = FBXSceneData()

    scene = ufbx.load_file(path)
    if not scene:
        raise RuntimeError(f"Failed to load FBX: {path}")

    # Extract ALL data in a single pass to avoid ufbx segfaults
    # IMPORTANT: ufbx crashes if we iterate over the same collection twice!
    # First, collect raw data from ufbx objects

    # Meshes - extract geometry data AND build mesh_id_to_idx in ONE iteration
    mesh_data_list = []
    mesh_id_to_idx = {}
    for i, mesh in enumerate(scene.meshes):
        mesh_id_to_idx[id(mesh)] = i
        if mesh.num_vertices == 0:
            continue

        # Triangulate
        tri_indices = []
        for face_idx in range(mesh.num_faces):
            face = mesh.faces[face_idx]
            begin = face.index_begin
            n = face.num_indices
            if n >= 3:
                v0 = mesh.vertex_indices[begin]
                for i in range(1, n - 1):
                    v1 = mesh.vertex_indices[begin + i]
                    v2 = mesh.vertex_indices[begin + i + 1]
                    tri_indices.append((v0, v1, v2))

        if not tri_indices:
            continue

        # Build vertex arrays
        vertices = []
        normals = []
        uvs = []

        has_normals = mesh.vertex_normal.values and len(mesh.vertex_normal.values) > 0
        has_uvs = mesh.uv_sets and len(mesh.uv_sets) > 0 and mesh.uv_sets[0].vertex_uv.values and len(mesh.uv_sets[0].vertex_uv.values) > 0

        for v0, v1, v2 in tri_indices:
            for idx in (v0, v1, v2):
                v = mesh.vertices[idx]
                vertices.append((v.x, v.y, v.z))

                if has_normals:
                    n_idx = mesh.vertex_normal.indices[idx]
                    n = mesh.vertex_normal.values[n_idx]
                    normals.append((n.x, n.y, n.z))

                if has_uvs:
                    vertex_uv = mesh.uv_sets[0].vertex_uv
                    uv_idx = vertex_uv.indices[idx]
                    uv = vertex_uv.values[uv_idx]
                    uvs.append((uv.x, uv.y))

        mesh_data_list.append({
            'name': mesh.name if mesh.name else "Mesh",
            'vertices': np.array(vertices, dtype=np.float32),
            'normals': np.array(normals, dtype=np.float32) if normals else None,
            'uvs': np.array(uvs, dtype=np.float32) if uvs else None,
        })

    # Nodes with meshes - extract transform data
    node_data_list = []
    stack = [scene.root_node] if scene.root_node else []
    while stack:
        node = stack.pop()
        if node.mesh:
            idx = mesh_id_to_idx.get(id(node.mesh))
            if idx is not None:
                t = node.local_transform
                node_data_list.append({
                    'name': node.name if node.name else f"Mesh_{idx}",
                    'mesh_idx': idx,
                    'translation': (t.translation.x, t.translation.y, t.translation.z),
                    'rotation': (t.rotation.x, t.rotation.y, t.rotation.z, t.rotation.w),
                    'scale': (t.scale.x, t.scale.y, t.scale.z),
                })

        for i in range(len(node.children)):
            stack.append(node.children[i])

    # Materials - extract color/texture info
    mat_data_list = []
    for mat in scene.materials:
        diffuse_color = None
        if mat.pbr.base_color.has_value:
            c = mat.pbr.base_color.value_vec4
            diffuse_color = (c.x, c.y, c.z, c.w)

        diffuse_texture = None
        if mat.pbr.base_color.texture and mat.pbr.base_color.texture.filename:
            diffuse_texture = mat.pbr.base_color.texture.filename

        mat_data_list.append({
            'name': mat.name if mat.name else "Material",
            'diffuse_color': diffuse_color,
            'diffuse_texture': diffuse_texture,
        })

    # Now build FBXSceneData from extracted data (no more ufbx access)

    # Materials
    for mat_data in mat_data_list:
        scene_data.materials.append(FBXMaterialData(
            name=mat_data['name'],
            diffuse_color=np.array(mat_data['diffuse_color'], dtype=np.float32) if mat_data['diffuse_color'] else None,
            diffuse_texture=mat_data['diffuse_texture'],
        ))

    # Meshes
    for i, mesh_data in enumerate(mesh_data_list):
        scene_data.meshes.append(FBXMeshData(
            name=mesh_data['name'],
            vertices=mesh_data['vertices'],
            normals=mesh_data['normals'],
            uvs=mesh_data['uvs'],
            indices=np.arange(len(mesh_data['vertices']), dtype=np.uint32),
            material_index=0,
        ))

    # Node hierarchy (flat)
    root = FBXNodeData("Root", children=[], mesh_indices=[], transform=np.eye(4, dtype=np.float32))
    for node_data in node_data_list:
        x, y, z, w = node_data['rotation']
        xx, yy, zz = x * x, y * y, z * z
        xy, xz, yz = x * y, x * z, y * z
        wx, wy, wz = w * x, w * y, w * z

        rot = np.array([
            [1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy)],
            [2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx)],
            [2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy)],
        ], dtype=np.float32)

        sx, sy, sz = node_data['scale']
        rot_scaled = rot * np.array([sx, sy, sz], dtype=np.float32)

        transform = np.eye(4, dtype=np.float32)
        transform[:3, :3] = rot_scaled
        transform[:3, 3] = node_data['translation']

        child = FBXNodeData(node_data['name'], children=[], mesh_indices=[node_data['mesh_idx']], transform=transform)
        root.children.append(child)

    scene_data.root = root

    return scene_data
