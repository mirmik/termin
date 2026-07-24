#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup


setup(
    name="termin-project-build",
    version="0.1.0",
    license="MIT",
    description="Packaged project build pipeline for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=find_namespace_packages(
        where="python",
        include=["termin.project_build", "termin.project_build.*"],
    ),
    package_dir={"": "python"},
    install_requires=[
        "tcbase",
        "termin-project",
        "termin-modules",
        "termin-default-assets",
        "termin-stdlib",
        "termin-glb",
        "termin-materials",
        "termin-shader-runtime",
        "tcgui",
        "packaging",
    ],
    zip_safe=False,
)
