#!/usr/bin/env python3

from setuptools import setup, find_packages
import os

directory = os.path.dirname(os.path.realpath(__file__))


if __name__ == "__main__":
    setup(
        name="termin",
        packages=find_packages(exclude=["tests", "tests.*", "examples", "examples.*"]),
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
                # Header files for external C++ module compilation
                "include/**/*.h",
                "include/**/*.hpp",
                # Standard library (shaders, materials, etc.)
                "resources/**/*",
            ]
        },
        include_package_data=True,
        install_requires=[
            "tcbase",
            "numpy",
            "PyOpenGL>=3.1",
            "glfw>=2.5.0",
            "Pillow>=9.0",
            "pyassimp",
            "scipy",
            "PyQt6>=6.4",
        ],
        zip_safe=False,
    )
