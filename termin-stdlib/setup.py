#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup


setup(
    name="termin-stdlib",
    version="0.1.0",
    license="MIT",
    description="Termin standard library resources and deployment helpers",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.10",
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
