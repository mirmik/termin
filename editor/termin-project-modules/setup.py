#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup
from termin_build.versioning import public_version


setup(
    name="termin-project-modules",
    version=public_version(),
    license="Apache-2.0",
    description="Project module runtime policy for Termin editor and player hosts",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=find_namespace_packages(
        where="python",
        include=["termin.project_modules", "termin.project_modules.*"],
    ),
    package_dir={"": "python"},
    install_requires=[
        "termin-base",
        "termin-engine",
        "termin-modules",
        "termin-nanobind",
        "termin-project",
        "termin-scene",
    ],
    zip_safe=False,
)
