#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup


setup(
    name="termin-qopt",
    version="0.1.0",
    license="MIT",
    description="Quadratic optimization, FEM, multibody dynamics, and robotics helpers for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.10",
    packages=find_namespace_packages(
        where="python",
        include=["termin.fem", "termin.fem.*", "termin.linalg", "termin.linalg.*", "termin.robot", "termin.robot.*"],
    ),
    package_dir={"": "python"},
    package_data={
        "termin.fem": ["README.md"],
    },
    install_requires=[
        "numpy",
        "scipy",
        "tcbase",
        "termin-components-kinematic",
    ],
    zip_safe=False,
)
