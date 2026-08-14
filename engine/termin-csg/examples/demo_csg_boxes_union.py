#!/usr/bin/env python3
"""Tiny script-CAD demo for termin-csg.

Run from a termin test venv:
    python termin-csg/examples/demo_csg_cad.py
"""

from termin.csg.cad import box, draw, translate


draw(box(4, 4, 2, center=True) - translate(box(2, 2, 2, center=True), 0, 0, 1))
