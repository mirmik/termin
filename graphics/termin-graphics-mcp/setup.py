#!/usr/bin/env python3

from setuptools import setup
from termin_build.versioning import public_version


setup(
    name="termin-graphics-mcp",
    version=public_version(),
    license="Apache-2.0",
    description="Graphics-owned MCP adapters for Termin render consumers",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.graphics.mcp"],
    package_dir={"termin.graphics.mcp": "termin/graphics/mcp"},
    install_requires=[
        "termin-mcp",
        "termin-image",
        "termin-graphics-core",
        "numpy",
    ],
    zip_safe=False,
)
