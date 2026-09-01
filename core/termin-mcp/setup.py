#!/usr/bin/env python3

from setuptools import setup


setup(
    name="termin-mcp",
    version="0.1.0",
    license="Apache-2.0",
    description="Shared MCP helpers for Termin runtime processes",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.mcp"],
    package_dir={"termin.mcp": "termin/mcp"},
    install_requires=[
        "termin-base",
    ],
    zip_safe=False,
)
