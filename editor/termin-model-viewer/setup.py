#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup
from termin_build.versioning import public_version


setup(
    name="termin-model-viewer",
    version=public_version(),
    license="Apache-2.0",
    description="Standalone GLB model viewer for the Termin SDK command line",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=find_namespace_packages(
        where="python",
        include=["termin.model_viewer", "termin.model_viewer.*"],
    ),
    package_dir={"": "python"},
    install_requires=[
        "numpy",
        "termin-base",
        "termin-graphics-core",
        "termin-glb",
        "termin-gui-native",
        "termin-image",
        "termin-visual-scene",
        "termin-window",
        "termin-mesh",
    ],
    zip_safe=False,
)
