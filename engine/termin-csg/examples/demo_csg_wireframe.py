#!/usr/bin/env python3
"""CSG wireframe demo.

Builds a small wall-with-door solid through termin.csg and displays its
triangle edges in a tcplot 3D widget.

Run from a termin test venv:
    python termin-csg/examples/demo_csg_wireframe.py
"""

from __future__ import annotations

import os
import sys

import numpy as np


_HERE = os.path.dirname(__file__)
_TERMIN_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_TCPLOT_EXAMPLES = os.path.join(_TERMIN_ROOT, "tcplot", "examples")
_TCPLOT_PYTHON = os.path.join(_TERMIN_ROOT, "tcplot", "python")
sys.path.insert(0, _TCPLOT_EXAMPLES)
sys.path.insert(0, _TCPLOT_PYTHON)

from tcplot import Plot3D
from termin.csg import make_box, subtract, extrude, to_mesh3
from _host import run_demo


def _mesh_edges(mesh):
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    triangles = np.asarray(mesh.triangles, dtype=np.uint32)
    edges = set()

    for a, b, c in triangles:
        for i, j in ((a, b), (b, c), (c, a)):
            lo = int(min(i, j))
            hi = int(max(i, j))
            edges.add((lo, hi))

    return vertices, sorted(edges)


def _plot_mesh_edges(plot, mesh, color, thickness=1.2):
    vertices, edges = _mesh_edges(mesh)
    for a, b in edges:
        p0 = vertices[a]
        p1 = vertices[b]
        plot.plot(
            np.array([p0[0], p1[0]], dtype=np.float64),
            np.array([p0[1], p1[1]], dtype=np.float64),
            np.array([p0[2], p1[2]], dtype=np.float64),
            color=color,
            thickness=thickness,
        )


def _make_wall_with_door():
    wall = make_box(8.0, 0.4, 3.0)
    doorway = make_box(1.5, 0.8, 2.2).translated(0.0, 0.0, -0.4)
    return subtract(wall, doorway)


def _make_extruded_frame():
    outer = [(-2.0, -1.4), (2.0, -1.4), (2.0, 1.4), (-2.0, 1.4)]
    hole = [(-0.75, -0.65), (0.75, -0.65), (0.75, 0.65), (-0.75, 0.65)]
    return extrude(outer, 0.7, holes=[hole]).translated(0.0, 2.0, -1.5)


def make_plot():
    wall = _make_wall_with_door()
    frame = _make_extruded_frame()

    wall_mesh = to_mesh3(wall, "wall_with_door")
    frame_mesh = to_mesh3(frame, "extruded_frame")

    plot = Plot3D()
    plot.data.title = (
        f"termin-csg: wall triangles={wall_mesh.triangle_count}, "
        f"frame triangles={frame_mesh.triangle_count}"
    )
    plot.set_axis_labels("X", "Y", "Z")
    plot.set_axis_scale(1.0, 1.0, 1.0)

    _plot_mesh_edges(plot, wall_mesh, color=(0.10, 0.72, 0.95, 1.0), thickness=1.6)
    _plot_mesh_edges(plot, frame_mesh, color=(1.00, 0.62, 0.16, 1.0), thickness=1.4)

    return plot


if __name__ == "__main__":
    run_demo("termin-csg - CSG Wireframe", make_plot, size=(1000, 760))
