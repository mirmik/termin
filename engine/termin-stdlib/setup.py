#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup
from termin_build.versioning import public_version


setup(
    name="termin-stdlib",
    version=public_version(),
    license="Apache-2.0",
    description="Termin standard library resources and deployment helpers",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=find_namespace_packages(where="python", include=["termin.stdlib", "termin.stdlib.*"]),
    package_dir={"": "python"},
    package_data={
        "termin.stdlib": [
            "resources/**/*",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
