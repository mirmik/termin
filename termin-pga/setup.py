#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup


setup(
    name="termin-pga",
    version="0.1.0",
    license="MIT",
    description="Archived projective-geometric algebra and geometry helpers for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=find_namespace_packages(
        where="python",
        include=["termin.ga201", "termin.ga201.*", "termin.geomalgo", "termin.geomalgo.*"],
    ),
    py_modules=["termin.algeom", "termin.closest", "termin.solve"],
    package_dir={"": "python"},
    install_requires=["numpy", "scipy", "tcbase"],
    zip_safe=False,
)
