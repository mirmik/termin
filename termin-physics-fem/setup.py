#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup


setup(
    name="termin-physics-fem",
    version="0.1.0",
    license="MIT",
    description="Experimental FEM scene physics components for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.10",
    packages=find_namespace_packages(
        where="python",
        include=["termin.physics_fem", "termin.physics_fem.*"],
    ),
    package_dir={"": "python"},
    install_requires=[
        "numpy",
        "tcbase",
        "termin-inspect",
        "termin-qopt",
        "termin-scene",
    ],
    zip_safe=False,
)
