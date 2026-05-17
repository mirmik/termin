#!/usr/bin/env python3
"""Preview 2D contours directly.

Run from a termin test venv:
    python termin-csg/examples/demo_csg_contours.py
"""

from termin.csg.cad import circle, draw, rect


outer = rect(5, 3)
slot = rect(1.2, 0.7).right(1.2).rZ(20)
round_hole = circle(0.45, segments=32).right(-1.35)

draw(outer - slot - round_hole, title="termin-csg - contours")
