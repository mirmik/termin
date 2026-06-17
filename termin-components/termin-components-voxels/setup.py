#!/usr/bin/env python3

from setuptools import setup


setup(
    name="termin-components-voxels",
    version="0.1.0",
    license="MIT",
    description="Voxel scene and render components for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.10",
    py_modules=[
        "termin.voxels.component",
        "termin.voxels.display_component",
        "termin.voxels.visualization",
        "termin.voxels.voxelizer_component",
    ],
    package_dir={"": "python"},
    install_requires=[
        "numpy",
        "tcbase",
        "tmesh",
        "termin-components-mesh",
        "termin-components-render",
        "termin-inspect",
        "termin-materials",
        "termin-render",
        "termin-scene",
        "termin-voxels",
    ],
    zip_safe=False,
)
