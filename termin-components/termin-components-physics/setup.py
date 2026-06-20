#!/usr/bin/env python3

from setuptools import setup


setup(
    name="termin-components-physics",
    version="0.1.0",
    license="MIT",
    description="Physics scene components for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.10",
    packages=["termin.physics_components"],
    package_dir={"termin.physics_components": "python/termin/physics_components"},
    install_requires=[
        "numpy",
        "tcbase",
        "termin-collision",
        "termin-inspect",
        "termin-physics",
        "termin-scene",
    ],
    zip_safe=False,
)
