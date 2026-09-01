#!/usr/bin/env python3

from setuptools import setup
from termin_build.versioning import public_version


setup(
    name="termin-components-voxels",
    version=public_version(),
    license="Apache-2.0",
    description="Voxel scene and render components for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=[
        "termin_voxel_components",
        "termin_voxel_component_specs",
    ],
    package_dir={"": "python"},
    install_requires=[
        "numpy",
        "termin-base",
        "termin-mesh",
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
