#!/usr/bin/env python3
"""Tiny script-CAD demo for termin-csg.

Run from a termin test venv:
    python termin-csg/examples/demo_csg_cad.py
"""

from termin.csg.cad import box, draw, sphere, cone


draw((sphere(1.3) ^ box(2, 2, 2, center=True)) + cone(1, 0, 2).up(1))
