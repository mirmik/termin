#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup


setup(
    name="termin-model-viewer",
    version="0.1.0",
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
        "tcbase",
        "tgfx",
        "termin-glb",
        "termin-gui-native",
        "termin-image",
        "termin-visual-scene",
        "termin-window",
        "tmesh",
    ],
    zip_safe=False,
)
