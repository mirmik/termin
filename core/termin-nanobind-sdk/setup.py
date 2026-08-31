#!/usr/bin/env python3

# termin-nanobind-sdk: pure-Python pip package.
#
# Ships only the `termin_nanobind` Python helpers (__init__.py + runtime.py
# for SDK discovery and library preloading). The ABI-specific nanobind shared
# library is NOT shipped here — the native product installs libnanobind.so or
# libnanobind-ft.so for its selected CPython ABI, and preload_sdk_libs resolves
# the logical "nanobind" request accordingly.

from setuptools import setup

setup(
    name="termin-nanobind",
    version="0.1.0",
    license="Apache-2.0",
    description="Runtime helpers for termin pip packages (SDK discovery, library preloading)",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin_nanobind"],
    package_dir={"termin_nanobind": "python/termin_nanobind"},
    zip_safe=False,
)
