#!/usr/bin/env python3

from setuptools import setup
from termin_build.versioning import public_version


setup(
    name="termin-shader-runtime",
    version=public_version(),
    license="Apache-2.0",
    description="Shared shader tool resolution and source-project runtime helpers",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    py_modules=[
        "termin.shader_runtime",
        "termin.shader_tools",
    ],
    package_dir={"": "."},
    install_requires=[
        "termin-base",
    ],
    zip_safe=False,
)
