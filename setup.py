#!/usr/bin/env python3

from wheel.bdist_wheel import bdist_wheel as bdist_wheel_
from setuptools import setup, Extension, Command
from distutils.util import get_platform

import glob
import sys
import os

directory = os.path.dirname(os.path.realpath(__file__))


setup(
    name="termin",
    packages=["termin"],
    python_requires='>3.10.0',
    version="0.0.0",
    license="MIT",
    description="Projective geometry library",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    url="https://github.com/mirmik/termin",
    long_description=open(os.path.join(
        directory, "README.md"), "r", encoding="utf8").read(),
    long_description_content_type="text/markdown",
    keywords=["testing", "cad"],
    classifiers=[],
    package_data={
        "termin": [
            "ga201/*",
            "physics/*",
            "colliders/*",
            "fem/*",
            "kinematic/*",
            "geombase/*",
            "utils/*",
            "geomalgo/*",
            "linalg/*",
            "robot/*",
            "loaders/*",
            "visualization/*",
            "visualization/**/*",
            "mesh/*",
        ]
    },
    include_package_data=True,
    install_requires=[
        "numpy",
        "PyOpenGL>=3.1",
        "glfw>=2.5.0",
        "Pillow>=9.0",
        "pyassimp"
    ],
    extras_require={
    },
    zip_safe=False,
)
