#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup


setup(
    name="termin-project",
    version="0.1.0",
    license="MIT",
    description="Project settings and project-root helpers for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.10",
    packages=find_namespace_packages(where="python", include=["termin.project", "termin.project.*"]),
    package_dir={"": "python"},
    install_requires=[
        "tcbase",
        "termin-render",
    ],
    zip_safe=False,
)
