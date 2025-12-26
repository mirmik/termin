"""
Native C++ voxelization wrapper.

Provides accelerated voxelization using the C++ implementation when available.
Falls back to Python implementation if native module not built.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
import numpy as np

# Try to import native module
try:
    from termin.voxels import _voxels_native
    HAS_NATIVE = True
except ImportError:
    _voxels_native = None
    HAS_NATIVE = False

if TYPE_CHECKING:
    from termin.mesh.mesh import Mesh3
    from termin.voxels.grid import VoxelGrid


def is_native_available() -> bool:
    """Check if native C++ voxelization is available."""
    return HAS_NATIVE


def voxelize_mesh_native(
    mesh: "Mesh3",
    cell_size: float = 0.25,
    fill_interior: bool = False,
    mark_surface: bool = False,
    clear_interior: bool = False,
    compute_normals: bool = False,
) -> "VoxelGrid":
    """
    Voxelize a mesh using native C++ implementation.

    Args:
        mesh: Input mesh to voxelize.
        cell_size: Size of each voxel.
        fill_interior: Fill interior voxels after surface voxelization.
        mark_surface: Mark surface voxels with VOXEL_SURFACE type.
        clear_interior: Remove interior (SOLID) voxels, keeping only surface.
        compute_normals: Compute surface normals for surface voxels.

    Returns:
        VoxelGrid with voxelization results.

    Raises:
        RuntimeError: If native module not available.
    """
    if not HAS_NATIVE:
        raise RuntimeError("Native voxelization module not available. Build with: cd cpp && mkdir build && cd build && cmake .. && make")

    from termin.voxels.grid import VoxelGrid
    from termin.voxels.voxelizer import VOXEL_SOLID, VOXEL_SURFACE

    vertices = mesh.vertices
    triangles = mesh.triangles

    if vertices is None or triangles is None:
        return VoxelGrid(origin=(0, 0, 0), cell_size=cell_size)

    # Ensure correct dtypes
    vertices = np.asarray(vertices, dtype=np.float64)
    triangles = np.asarray(triangles, dtype=np.int32)

    # Create native grid
    from termin.geombase._geom_native import Vec3
    native_grid = _voxels_native.VoxelGrid(cell_size, Vec3(0, 0, 0))

    # Voxelize
    voxel_count = native_grid.voxelize_mesh(vertices, triangles, VOXEL_SOLID)
    print(f"Native voxelization: {voxel_count} surface voxels")

    # Fill interior
    if fill_interior:
        filled = native_grid.fill_interior(VOXEL_SOLID)
        print(f"Native fill_interior: {filled} voxels")

    # Mark surface
    if mark_surface:
        marked = native_grid.mark_surface(VOXEL_SURFACE)
        print(f"Native mark_surface: {marked} voxels")

    # Clear interior
    if clear_interior:
        cleared = native_grid.clear_by_type(VOXEL_SOLID)
        print(f"Native clear_by_type: {cleared} voxels")

    # Compute normals
    if compute_normals:
        normals_count = native_grid.compute_surface_normals(vertices, triangles)
        print(f"Native compute_surface_normals: {normals_count} normals")

    # Convert to Python VoxelGrid
    py_grid = VoxelGrid(origin=(0, 0, 0), cell_size=cell_size)

    for vx, vy, vz, vtype in native_grid.iter_non_empty():
        py_grid.set(vx, vy, vz, vtype)

    # Copy surface normals (list of normals per voxel)
    native_normals = native_grid.surface_normals
    for key, normals_list in native_normals.items():
        vx, vy, vz = key
        py_grid.set_surface_normals(vx, vy, vz, list(normals_list))

    return py_grid


def benchmark_voxelization(mesh: "Mesh3", cell_size: float = 0.25, iterations: int = 3):
    """
    Benchmark native vs Python voxelization.

    Args:
        mesh: Mesh to voxelize.
        cell_size: Voxel size.
        iterations: Number of iterations for timing.
    """
    import time
    from termin.voxels.grid import VoxelGrid
    from termin.voxels.voxelizer import MeshVoxelizer

    vertices = mesh.vertices
    triangles = mesh.triangles

    if vertices is None or triangles is None:
        print("Mesh has no geometry")
        return

    print(f"Mesh: {len(vertices)} vertices, {len(triangles)} triangles")
    print(f"Cell size: {cell_size}")
    print(f"Iterations: {iterations}")
    print()

    # Python benchmark
    print("Python voxelization:")
    py_times = []
    py_voxel_count = 0
    for i in range(iterations):
        grid = VoxelGrid(origin=(0, 0, 0), cell_size=cell_size)
        voxelizer = MeshVoxelizer(grid)
        start = time.perf_counter()
        voxelizer.voxelize_mesh(mesh, transform_matrix=None)
        elapsed = time.perf_counter() - start
        py_times.append(elapsed)
        py_voxel_count = grid.voxel_count
        print(f"  Run {i+1}: {elapsed:.4f}s ({py_voxel_count} voxels)")
    py_avg = sum(py_times) / len(py_times)
    print(f"  Average: {py_avg:.4f}s")
    print()

    # Native benchmark
    if HAS_NATIVE:
        print("Native voxelization:")
        native_times = []
        native_voxel_count = 0
        vertices_f64 = np.asarray(vertices, dtype=np.float64)
        triangles_i32 = np.asarray(triangles, dtype=np.int32)

        from termin.geombase._geom_native import Vec3

        for i in range(iterations):
            native_grid = _voxels_native.VoxelGrid(cell_size, Vec3(0, 0, 0))
            start = time.perf_counter()
            native_grid.voxelize_mesh(vertices_f64, triangles_i32)
            elapsed = time.perf_counter() - start
            native_times.append(elapsed)
            native_voxel_count = native_grid.voxel_count()
            print(f"  Run {i+1}: {elapsed:.4f}s ({native_voxel_count} voxels)")
        native_avg = sum(native_times) / len(native_times)
        print(f"  Average: {native_avg:.4f}s")
        print()

        speedup = py_avg / native_avg if native_avg > 0 else float('inf')
        print(f"Speedup: {speedup:.1f}x")
    else:
        print("Native module not available")
