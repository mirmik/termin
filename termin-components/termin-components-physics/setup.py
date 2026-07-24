#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup


setup(
    name="termin-components-physics",
    version="0.1.0",
    license="MIT",
    description="Physics scene components for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=[
        *find_namespace_packages(
            where="python",
            include=["termin.physics_components", "termin.physics_components.*"],
        ),
        "termin_physics_component_specs",
    ],
    package_dir={"": "python"},
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
