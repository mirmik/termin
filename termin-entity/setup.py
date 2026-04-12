#!/usr/bin/env python3

# termin-entity is a transitional pip facade.
#
# The C++ _entity_native binding currently lives inside main termin's build
# (termin/cpp/python_bindings.cmake). This pip package does NOT build C++; it
# copies the already-built _entity_native.so from $TERMIN_SDK into its own
# package directory via TerminCMakeBuildExt (thin SDK-copy mode).
#
# Pending future C++ decomposition — the _entity_native module currently
# bundles entity/scene core plus OrbitCamera, input events, and TcScene
# helpers, which should eventually be split into narrower modules.

from setuptools import setup, Extension
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    module_names = ["_entity_native"]
    source_dir = _DIR


setup(
    name="termin-entity",
    version="0.1.0",
    license="MIT",
    description="Entity and Component Python bindings (thin; requires termin SDK at runtime)",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin.entity"],
    package_dir={"termin.entity": "python/termin/entity"},
    install_requires=["termin-nanobind"],
    ext_modules=[
        Extension("termin.entity._entity_native", sources=[]),
    ],
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
