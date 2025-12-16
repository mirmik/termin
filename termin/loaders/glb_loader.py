# termin/loaders/glb_loader.py
"""GLB/glTF 2.0 loader.

Pure Python implementation without external dependencies (except numpy).
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import List, Optional, Dict, Any

import numpy as np


# ---------- DATA CLASSES ----------

class GLBMeshData:
    """Mesh data extracted from GLB."""
    def __init__(self, name: str, vertices: np.ndarray, normals: Optional[np.ndarray],
                 uvs: Optional[np.ndarray], indices: np.ndarray, material_index: int):
        self.name = name
        self.vertices = vertices
        self.normals = normals
        self.uvs = uvs
        self.indices = indices
        self.material_index = material_index


class GLBMaterialData:
    """Material data extracted from GLB."""
    def __init__(self, name: str, base_color: Optional[np.ndarray] = None,
                 base_color_texture: Optional[int] = None):
        self.name = name
        self.base_color = base_color  # RGBA
        self.base_color_texture = base_color_texture  # texture index


class GLBTextureData:
    """Texture data extracted from GLB."""
    def __init__(self, name: str, data: bytes, mime_type: str):
        self.name = name
        self.data = data  # Raw image bytes (PNG/JPEG)
        self.mime_type = mime_type


class GLBAnimationChannel:
    """Animation channel for a single node."""
    def __init__(self, node_index: int, node_name: str,
                 pos_keys: List, rot_keys: List, scale_keys: List):
        self.node_index = node_index
        self.node_name = node_name
        self.pos_keys = pos_keys      # [(time, [x,y,z]), ...]
        self.rot_keys = rot_keys      # [(time, [x,y,z,w]), ...] quaternion
        self.scale_keys = scale_keys  # [(time, [x,y,z]), ...]


class GLBAnimationClip:
    """Animation clip containing multiple channels."""
    def __init__(self, name: str, channels: List[GLBAnimationChannel], duration: float):
        self.name = name
        self.channels = channels
        self.duration = duration


class GLBNodeData:
    """Node in scene hierarchy."""
    def __init__(self, name: str, children: List[int], mesh_index: Optional[int],
                 translation: np.ndarray, rotation: np.ndarray, scale: np.ndarray):
        self.name = name
        self.children = children
        self.mesh_index = mesh_index
        self.translation = translation  # [x, y, z]
        self.rotation = rotation        # [x, y, z, w] quaternion
        self.scale = scale              # [x, y, z]


class GLBSceneData:
    """Complete scene data from GLB file."""
    def __init__(self):
        self.meshes: List[GLBMeshData] = []
        self.materials: List[GLBMaterialData] = []
        self.textures: List[GLBTextureData] = []
        self.animations: List[GLBAnimationClip] = []
        self.nodes: List[GLBNodeData] = []
        self.root_nodes: List[int] = []
        # Map from glTF mesh index to list of our internal mesh indices
        # (one glTF mesh can have multiple primitives)
        self.mesh_index_map: Dict[int, List[int]] = {}


# ---------- ACCESSOR HELPERS ----------

COMPONENT_TYPE_SIZE = {
    5120: 1,  # BYTE
    5121: 1,  # UNSIGNED_BYTE
    5122: 2,  # SHORT
    5123: 2,  # UNSIGNED_SHORT
    5125: 4,  # UNSIGNED_INT
    5126: 4,  # FLOAT
}

COMPONENT_TYPE_DTYPE = {
    5120: np.int8,
    5121: np.uint8,
    5122: np.int16,
    5123: np.uint16,
    5125: np.uint32,
    5126: np.float32,
}

TYPE_NUM_COMPONENTS = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16,
}


def _read_accessor(gltf: dict, bin_data: bytes, accessor_index: int) -> np.ndarray:
    """Read data from an accessor."""
    accessor = gltf["accessors"][accessor_index]
    buffer_view = gltf["bufferViews"][accessor["bufferView"]]

    component_type = accessor["componentType"]
    accessor_type = accessor["type"]
    count = accessor["count"]

    dtype = COMPONENT_TYPE_DTYPE[component_type]
    num_components = TYPE_NUM_COMPONENTS[accessor_type]

    byte_offset = buffer_view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    byte_stride = buffer_view.get("byteStride", 0)

    element_size = COMPONENT_TYPE_SIZE[component_type] * num_components

    if byte_stride == 0 or byte_stride == element_size:
        # Tightly packed
        data = np.frombuffer(
            bin_data, dtype=dtype,
            offset=byte_offset,
            count=count * num_components
        )
        if num_components > 1:
            data = data.reshape(count, num_components)
    else:
        # Strided data
        data = np.zeros((count, num_components), dtype=dtype)
        for i in range(count):
            offset = byte_offset + i * byte_stride
            element = np.frombuffer(bin_data, dtype=dtype, offset=offset, count=num_components)
            data[i] = element

    return data.astype(np.float32) if dtype != np.float32 else data


# ---------- PARSING FUNCTIONS ----------

def _parse_meshes(gltf: dict, bin_data: bytes, scene_data: GLBSceneData):
    """Parse all meshes from glTF."""
    for mesh_idx, mesh in enumerate(gltf.get("meshes", [])):
        mesh_name = mesh.get("name", f"Mesh_{mesh_idx}")
        scene_data.mesh_index_map[mesh_idx] = []

        for prim_idx, primitive in enumerate(mesh.get("primitives", [])):
            attributes = primitive.get("attributes", {})

            # Vertices (required)
            if "POSITION" not in attributes:
                continue
            vertices = _read_accessor(gltf, bin_data, attributes["POSITION"])

            # Normals (optional)
            normals = None
            if "NORMAL" in attributes:
                normals = _read_accessor(gltf, bin_data, attributes["NORMAL"])

            # UVs (optional)
            uvs = None
            if "TEXCOORD_0" in attributes:
                uvs = _read_accessor(gltf, bin_data, attributes["TEXCOORD_0"])

            # Indices
            if "indices" in primitive:
                indices = _read_accessor(gltf, bin_data, primitive["indices"]).astype(np.uint32)
                if indices.ndim > 1:
                    indices = indices.flatten()
            else:
                # No indices - sequential
                indices = np.arange(len(vertices), dtype=np.uint32)

            # Material
            material_index = primitive.get("material", 0)

            # Build expanded vertex arrays (for compatibility with FBX loader output)
            expanded_verts = vertices[indices]
            expanded_normals = normals[indices] if normals is not None else None
            expanded_uvs = uvs[indices] if uvs is not None else None

            prim_name = mesh_name if prim_idx == 0 else f"{mesh_name}_{prim_idx}"

            our_mesh_idx = len(scene_data.meshes)
            scene_data.mesh_index_map[mesh_idx].append(our_mesh_idx)

            scene_data.meshes.append(GLBMeshData(
                name=prim_name,
                vertices=expanded_verts.astype(np.float32),
                normals=expanded_normals.astype(np.float32) if expanded_normals is not None else None,
                uvs=expanded_uvs.astype(np.float32) if expanded_uvs is not None else None,
                indices=np.arange(len(expanded_verts), dtype=np.uint32),
                material_index=material_index,
            ))


def _parse_materials(gltf: dict, scene_data: GLBSceneData):
    """Parse all materials from glTF."""
    for mat_idx, mat in enumerate(gltf.get("materials", [])):
        name = mat.get("name", f"Material_{mat_idx}")

        base_color = None
        base_color_texture = None

        pbr = mat.get("pbrMetallicRoughness", {})
        if "baseColorFactor" in pbr:
            base_color = np.array(pbr["baseColorFactor"], dtype=np.float32)
        if "baseColorTexture" in pbr:
            base_color_texture = pbr["baseColorTexture"].get("index")

        scene_data.materials.append(GLBMaterialData(
            name=name,
            base_color=base_color,
            base_color_texture=base_color_texture,
        ))


def _parse_textures(gltf: dict, bin_data: bytes, scene_data: GLBSceneData):
    """Parse all textures/images from glTF."""
    images = gltf.get("images", [])

    for tex_idx, texture in enumerate(gltf.get("textures", [])):
        source_idx = texture.get("source")
        if source_idx is None or source_idx >= len(images):
            continue

        image = images[source_idx]
        name = image.get("name", f"Texture_{tex_idx}")
        mime_type = image.get("mimeType", "image/png")

        # Get image data
        data = None
        if "bufferView" in image:
            bv = gltf["bufferViews"][image["bufferView"]]
            offset = bv.get("byteOffset", 0)
            length = bv["byteLength"]
            data = bin_data[offset:offset + length]
        elif "uri" in image:
            # External or data URI - skip for now
            continue

        if data:
            scene_data.textures.append(GLBTextureData(
                name=name,
                data=data,
                mime_type=mime_type,
            ))


def _parse_nodes(gltf: dict, scene_data: GLBSceneData):
    """Parse node hierarchy."""
    for node_idx, node in enumerate(gltf.get("nodes", [])):
        name = node.get("name", f"Node_{node_idx}")
        children = node.get("children", [])
        mesh_index = node.get("mesh")

        # Transform
        translation = np.array(node.get("translation", [0, 0, 0]), dtype=np.float32)
        rotation = np.array(node.get("rotation", [0, 0, 0, 1]), dtype=np.float32)  # xyzw
        scale = np.array(node.get("scale", [1, 1, 1]), dtype=np.float32)

        # If matrix is provided, decompose it (simplified - just use TRS if available)
        if "matrix" in node and "translation" not in node:
            # TODO: decompose matrix if needed
            pass

        scene_data.nodes.append(GLBNodeData(
            name=name,
            children=children,
            mesh_index=mesh_index,
            translation=translation,
            rotation=rotation,
            scale=scale,
        ))

    # Root nodes from default scene
    scenes = gltf.get("scenes", [])
    default_scene = gltf.get("scene", 0)
    if scenes and default_scene < len(scenes):
        scene_data.root_nodes = scenes[default_scene].get("nodes", [])


def _parse_animations(gltf: dict, bin_data: bytes, scene_data: GLBSceneData):
    """Parse animations from glTF."""
    nodes = gltf.get("nodes", [])

    for anim_idx, anim in enumerate(gltf.get("animations", [])):
        anim_name = anim.get("name", f"Animation_{anim_idx}")

        # Group channels by target node
        node_channels: Dict[int, Dict[str, Any]] = {}

        for channel in anim.get("channels", []):
            sampler_idx = channel["sampler"]
            sampler = anim["samplers"][sampler_idx]

            target = channel["target"]
            node_idx = target.get("node")
            path = target.get("path")  # translation, rotation, scale, weights

            if node_idx is None or path not in ("translation", "rotation", "scale"):
                continue

            # Read input (times) and output (values)
            times = _read_accessor(gltf, bin_data, sampler["input"])
            values = _read_accessor(gltf, bin_data, sampler["output"])

            if times.ndim > 1:
                times = times.flatten()

            if node_idx not in node_channels:
                node_channels[node_idx] = {
                    "pos_keys": [],
                    "rot_keys": [],
                    "scale_keys": [],
                }

            # Build keyframe list
            keys = []
            for i, t in enumerate(times):
                if values.ndim == 1:
                    v = values[i:i+1]
                else:
                    v = values[i]
                keys.append((float(t), v.copy()))

            if path == "translation":
                node_channels[node_idx]["pos_keys"] = keys
            elif path == "rotation":
                node_channels[node_idx]["rot_keys"] = keys
            elif path == "scale":
                node_channels[node_idx]["scale_keys"] = keys

        # Build animation channels
        channels = []
        max_time = 0.0

        for node_idx, ch_data in node_channels.items():
            node_name = nodes[node_idx].get("name", f"Node_{node_idx}") if node_idx < len(nodes) else f"Node_{node_idx}"

            # Track max time for duration
            for keys in [ch_data["pos_keys"], ch_data["rot_keys"], ch_data["scale_keys"]]:
                if keys:
                    max_time = max(max_time, keys[-1][0])

            channels.append(GLBAnimationChannel(
                node_index=node_idx,
                node_name=node_name,
                pos_keys=ch_data["pos_keys"],
                rot_keys=ch_data["rot_keys"],
                scale_keys=ch_data["scale_keys"],
            ))

        if channels:
            scene_data.animations.append(GLBAnimationClip(
                name=anim_name,
                channels=channels,
                duration=max_time,
            ))


# ---------- PUBLIC API ----------

def load_glb_file(path: str | Path) -> GLBSceneData:
    """Load a GLB file and return scene data.

    Args:
        path: Path to .glb file

    Returns:
        GLBSceneData containing meshes, materials, textures, animations, nodes
    """
    path = Path(path)

    with open(path, "rb") as f:
        data = f.read()

    # Parse header
    if len(data) < 12:
        raise ValueError("File too small to be valid GLB")

    magic = data[0:4]
    if magic != b"glTF":
        raise ValueError(f"Invalid GLB magic: {magic}")

    version, length = struct.unpack("<II", data[4:12])
    if version != 2:
        raise ValueError(f"Unsupported glTF version: {version}")

    # Parse chunks
    offset = 12
    json_data = None
    bin_data = None

    while offset < len(data):
        if offset + 8 > len(data):
            break

        chunk_length, chunk_type = struct.unpack("<II", data[offset:offset + 8])
        chunk_data = data[offset + 8:offset + 8 + chunk_length]

        if chunk_type == 0x4E4F534A:  # JSON
            json_data = chunk_data.decode("utf-8")
        elif chunk_type == 0x004E4942:  # BIN
            bin_data = chunk_data

        # Align to 4 bytes
        offset += 8 + chunk_length
        offset = (offset + 3) & ~3

    if json_data is None:
        raise ValueError("No JSON chunk found in GLB")

    gltf = json.loads(json_data)
    bin_data = bin_data or b""

    # Parse scene
    scene_data = GLBSceneData()

    _parse_nodes(gltf, scene_data)
    _parse_materials(gltf, scene_data)
    _parse_textures(gltf, bin_data, scene_data)
    _parse_meshes(gltf, bin_data, scene_data)
    _parse_animations(gltf, bin_data, scene_data)

    return scene_data
