#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup
from termin_build.versioning import public_version


setup(
    name="termin-glb",
    version=public_version(),
    license="Apache-2.0",
    description="Portable GLB/glTF decoding and runtime publication",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=find_namespace_packages(where="python", include=["termin.glb", "termin.glb.*"]),
    package_dir={"": "python"},
    install_requires=[
        "termin-glb-native",
        "termin-base",
        "termin-mesh",
        "termin-skeleton",
        "termin-animation",
        "termin-nanobind",
        "numpy",
    ],
    zip_safe=False,
)
