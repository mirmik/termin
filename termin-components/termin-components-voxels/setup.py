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
    packages=[
        "termin_voxel_components",
        "termin_voxel_component_specs",
    ],
    package_dir={"": "python"},
    install_requires=[
        "numpy",
        "tcbase",
        "tmesh",
        "termin-assets",
        "termin-components-mesh",
        "termin-components-render",
        "termin-inspect",
        "termin-materials",
        "termin-navmesh",
        "termin-render",
        "termin-scene",
        "termin-voxels",
    ],
    zip_safe=False,
)
