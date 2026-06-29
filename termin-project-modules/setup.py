#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup


setup(
    name="termin-project-modules",
    version="0.1.0",
    license="MIT",
    description="Project module runtime policy for Termin editor and player hosts",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.10",
    packages=find_namespace_packages(
        where="python",
        include=["termin.project_modules", "termin.project_modules.*"],
    ),
    package_dir={"": "python"},
    install_requires=[
        "tcbase",
        "termin-engine",
        "termin-modules",
        "termin-nanobind",
        "termin-project",
        "termin-scene",
    ],
    zip_safe=False,
)
