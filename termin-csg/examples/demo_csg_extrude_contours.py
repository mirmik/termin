#!/usr/bin/env python3
"""Extrude 2D contours into solids.

Run from a termin test venv:
    python termin-csg/examples/demo_csg_extrude_contours.py
"""

from termin.csg.cad import circle, cylinder, draw, rect


plate_profile = rect(5, 3) - rect(1.2, 0.7).right(1.2).rZ(20) - circle(0.45, segments=32).right(-1.35)
plate = plate_profile.extrude(0.35)
peg = cylinder(0.25, 1.0, segments=32).up(0.5).right(-1.35)

draw(plate + peg, title="termin-csg - extruded contours")
