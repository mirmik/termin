"""FBX extractor - extracts meshes and textures from FBX files."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import numpy as np

from tcbase import log
from termin.loaders.fbx_loader import load_fbx_file, FBXMeshData


def save_mesh_as_obj(mesh: FBXMeshData, output_path: Path) -> None:
    """Save mesh data as OBJ file.

    Args:
        mesh: FBXMeshData with vertices, normals, uvs
        output_path: Path to save the .obj file
    """
    lines = []
    lines.append(f"# Extracted from FBX: {mesh.name}")
    lines.append(f"# Vertices: {len(mesh.vertices)}")
    lines.append("")

    # Vertices are already expanded (one per face corner)
    # OBJ format: v x y z
    for v in mesh.vertices:
        lines.append(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")

    lines.append("")

    # Texture coordinates: vt u v
    if mesh.uvs is not None and len(mesh.uvs) > 0:
        for uv in mesh.uvs:
            lines.append(f"vt {uv[0]:.6f} {uv[1]:.6f}")
        lines.append("")

    # Normals: vn x y z
    if mesh.normals is not None and len(mesh.normals) > 0:
        for n in mesh.normals:
            lines.append(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}")
        lines.append("")

    # Faces - vertices are already triangulated and expanded
    # So indices are simply sequential: 0,1,2, 3,4,5, etc.
    num_triangles = len(mesh.vertices) // 3
    has_uvs = mesh.uvs is not None and len(mesh.uvs) > 0
    has_normals = mesh.normals is not None and len(mesh.normals) > 0

    for i in range(num_triangles):
        base = i * 3
        # OBJ indices are 1-based
        i1, i2, i3 = base + 1, base + 2, base + 3

        if has_uvs and has_normals:
            lines.append(f"f {i1}/{i1}/{i1} {i2}/{i2}/{i2} {i3}/{i3}/{i3}")
        elif has_uvs:
            lines.append(f"f {i1}/{i1} {i2}/{i2} {i3}/{i3}")
        elif has_normals:
            lines.append(f"f {i1}//{i1} {i2}//{i2} {i3}//{i3}")
        else:
            lines.append(f"f {i1} {i2} {i3}")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def extract_fbx(fbx_path: Path, output_dir: Path = None) -> Tuple[Path, List[Path]]:
    """Extract meshes and textures from FBX file into a directory.

    Args:
        fbx_path: Path to the FBX file
        output_dir: Directory to extract to. If None, creates directory
                   next to FBX with same name.

    Returns:
        Tuple of (output_directory, list_of_created_files)
    """
    fbx_path = Path(fbx_path)

    if output_dir is None:
        output_dir = fbx_path.parent / fbx_path.stem

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load FBX
    scene_data = load_fbx_file(str(fbx_path))

    created_files = []

    # Extract meshes
    for mesh in scene_data.meshes:
        # Sanitize mesh name for filename
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in mesh.name)
        if not safe_name:
            safe_name = f"mesh_{len(created_files)}"

        obj_path = output_dir / f"{safe_name}.obj"
        save_mesh_as_obj(mesh, obj_path)
        created_files.append(obj_path)
        log.info(f"[FBX Extract] Saved mesh: {obj_path.name}")

    # Extract embedded textures
    textures_dir = None
    for tex in scene_data.textures:
        if tex.content is None:
            continue  # External texture, skip

        # Create textures subdirectory on first embedded texture
        if textures_dir is None:
            textures_dir = output_dir / "textures"
            textures_dir.mkdir(exist_ok=True)

        # Determine filename from original path or texture name
        if tex.filename:
            tex_filename = Path(tex.filename).name
        else:
            tex_filename = tex.name if tex.name else f"texture_{len(created_files)}"
            # Add extension based on content signature
            if tex.content[:4] == b'\x89PNG':
                tex_filename += ".png"
            elif tex.content[:2] == b'\xff\xd8':
                tex_filename += ".jpg"
            else:
                tex_filename += ".bin"

        # Sanitize filename
        safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in tex_filename)
        tex_path = textures_dir / safe_name

        tex_path.write_bytes(tex.content)
        created_files.append(tex_path)
        log.info(f"[FBX Extract] Saved texture: {tex_path.name} ({len(tex.content)} bytes)")

    # Save material info as reference
    if scene_data.materials:
        mat_info_path = output_dir / "_materials.txt"
        lines = ["# Materials from FBX", ""]
        for mat in scene_data.materials:
            lines.append(f"Material: {mat.name}")
            if mat.diffuse_color is not None:
                c = mat.diffuse_color
                lines.append(f"  Diffuse: ({c[0]:.3f}, {c[1]:.3f}, {c[2]:.3f}, {c[3]:.3f})")
            if mat.diffuse_texture:
                lines.append(f"  Texture: {mat.diffuse_texture}")
            lines.append("")
        mat_info_path.write_text("\n".join(lines), encoding="utf-8")
        created_files.append(mat_info_path)
        log.info(f"[FBX Extract] Saved materials info: {mat_info_path.name}")

    embedded_tex_count = sum(1 for t in scene_data.textures if t.content is not None)
    log.info(f"[FBX Extract] Extracted {len(scene_data.meshes)} meshes, {embedded_tex_count} textures to {output_dir}")

    # Extract animations
    anim_files = extract_animations(fbx_path, output_dir, scene_data)
    created_files.extend(anim_files)

    return output_dir, created_files


def extract_animations(
    fbx_path: Path,
    output_dir: Path = None,
    scene_data=None,
) -> List[Path]:
    """Extract animations from FBX file into .tanim files.

    Args:
        fbx_path: Path to the FBX file
        output_dir: Directory to extract to. If None, creates directory
                   next to FBX with same name.
        scene_data: Pre-loaded FBXSceneData (optional, avoids reloading)

    Returns:
        List of created animation files
    """
    from termin.visualization.animation.clip import clip_from_fbx
    from termin.visualization.animation.clip_io import save_animation_clip

    fbx_path = Path(fbx_path)

    if output_dir is None:
        output_dir = fbx_path.parent / fbx_path.stem

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load FBX if not provided
    if scene_data is None:
        scene_data = load_fbx_file(str(fbx_path))

    created_files = []

    # Extract animations
    for fbx_anim in scene_data.animations:
        # Convert FBX animation to AnimationClip
        clip = clip_from_fbx(fbx_anim)

        # Sanitize name for filename
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in clip.name)
        if not safe_name:
            safe_name = f"animation_{len(created_files)}"

        anim_path = output_dir / f"{safe_name}.tanim"
        save_animation_clip(clip, anim_path)
        created_files.append(anim_path)
        log.info(f"[FBX Extract] Saved animation: {anim_path.name} ({clip.duration:.2f}s, {len(clip.channels)} channels)")

    if created_files:
        log.info(f"[FBX Extract] Extracted {len(created_files)} animation(s)")

    return created_files
