# Termin - Top-level CMakeLists.txt
# Builds the entire project as a C++ application with embedded Python
#
# Usage (standalone build):
#   mkdir build && cd build
#   cmake .. -DBUILD_EDITOR_MINIMAL=ON -DBUNDLE_PYTHON=ON
#   cmake --build . --parallel
#   cmake --install .
#
# To run:
#   ./install/bin/termin_editor
#
# Structure after install:
#   install/
#     bin/termin_editor
#     lib/
#       libpython3.10.so      (bundled Python, if BUNDLE_PYTHON=ON)
#       python3.10/           (stdlib + site-packages)
#       python/termin/        (our modules + native extensions)

cmake_minimum_required(VERSION 3.16)
project(termin VERSION 0.1.0 LANGUAGES C CXX)

# Options (passed to cpp/CMakeLists.txt)
option(BUILD_EDITOR_MINIMAL "Build minimal editor (embedded Python, PyQt6)" ON)
option(BUILD_EDITOR_EXE "Build Qt C++ editor (requires Qt SDK)" OFF)
option(BUILD_TESTS "Build C++ tests" OFF)
option(BUILD_CSHARP_BINDINGS "Build C# SWIG bindings" OFF)
option(BUNDLE_PYTHON "Bundle Python runtime for standalone distribution" OFF)

# Set project root for subprojects
set(TERMIN_ROOT ${CMAKE_CURRENT_SOURCE_DIR})

# Default install prefix to ./install if not specified
if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
    set(CMAKE_INSTALL_PREFIX "${CMAKE_CURRENT_SOURCE_DIR}/install" CACHE PATH "Install prefix" FORCE)
endif()

# Find Python (needed for bundling info)
find_package(Python COMPONENTS Interpreter Development REQUIRED)

# Add the main C++ subproject
# cpp/CMakeLists.txt handles all native modules and libraries
add_subdirectory(cpp)

# Post-install: copy Python sources to install directory for embedded Python
# Native modules (.so/.dll) are already installed by cpp/CMakeLists.txt
# This copies Python source files alongside them
install(DIRECTORY ${TERMIN_ROOT}/termin/
    DESTINATION ${CMAKE_INSTALL_PREFIX}/lib/python/termin
    PATTERN "__pycache__" EXCLUDE
    PATTERN "*.pyc" EXCLUDE
    PATTERN "*.pyo" EXCLUDE
    PATTERN "*.so" EXCLUDE
    PATTERN "*.dll" EXCLUDE
    PATTERN "*.dylib" EXCLUDE
    PATTERN "*.egg-info" EXCLUDE
)

# Bundle Python runtime if requested
if(BUNDLE_PYTHON)
    # Get Python paths
    execute_process(
        COMMAND ${Python_EXECUTABLE} -c "import sys; print(sys.prefix)"
        OUTPUT_VARIABLE PYTHON_PREFIX
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    execute_process(
        COMMAND ${Python_EXECUTABLE} -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        OUTPUT_VARIABLE PYTHON_VERSION
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )

    set(PYTHON_LIBDIR "${PYTHON_PREFIX}/lib")
    set(PYTHON_STDLIB "${PYTHON_LIBDIR}/python${PYTHON_VERSION}")

    message(STATUS "Will bundle Python ${PYTHON_VERSION} from ${PYTHON_PREFIX}")

    # Install libpython
    install(DIRECTORY ${PYTHON_LIBDIR}/
        DESTINATION ${CMAKE_INSTALL_PREFIX}/lib
        FILES_MATCHING
        PATTERN "libpython${PYTHON_VERSION}*.so*"
        PATTERN "python${PYTHON_VERSION}" EXCLUDE
    )

    # Install Python standard library (excluding heavy/unneeded parts)
    install(DIRECTORY ${PYTHON_STDLIB}/
        DESTINATION ${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        PATTERN "*.pyo" EXCLUDE
        PATTERN "test" EXCLUDE
        PATTERN "tests" EXCLUDE
        PATTERN "idle_test" EXCLUDE
        PATTERN "tkinter" EXCLUDE
        PATTERN "turtledemo" EXCLUDE
        PATTERN "lib2to3" EXCLUDE
        PATTERN "ensurepip" EXCLUDE
        PATTERN "site-packages" EXCLUDE
    )

    # Create site-packages and install dependencies
    # List packages to bundle (extend as needed)
    set(BUNDLE_PACKAGES
        numpy
        PyQt6
        PyQt6_sip.cpython-310-x86_64-linux-gnu.so
        sip
        sipbuild
        PIL
        Pillow
        scipy
        glfw
        OpenGL
        pyassimp
        pyopengl
        sdl2
        ctypes
        yaml
        _yaml
    )

    # Install each package
    foreach(pkg ${BUNDLE_PACKAGES})
        if(EXISTS "${PYTHON_STDLIB}/site-packages/${pkg}")
            install(DIRECTORY "${PYTHON_STDLIB}/site-packages/${pkg}"
                DESTINATION ${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages
                PATTERN "__pycache__" EXCLUDE
                PATTERN "*.pyc" EXCLUDE
            )
        endif()
        # Also copy .dist-info directories
        file(GLOB DIST_INFOS "${PYTHON_STDLIB}/site-packages/${pkg}*.dist-info")
        foreach(di ${DIST_INFOS})
            install(DIRECTORY ${di}
                DESTINATION ${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages
            )
        endforeach()
    endforeach()

    # Copy standalone .so files (like PyQt6_sip)
    file(GLOB STANDALONE_SOS "${PYTHON_STDLIB}/site-packages/*.so")
    install(FILES ${STANDALONE_SOS}
        DESTINATION ${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages
    )

    # Copy .libs directories (numpy.libs, scipy.libs, pillow.libs contain vendored shared libs)
    foreach(pkg numpy scipy pillow)
        if(EXISTS "${PYTHON_STDLIB}/site-packages/${pkg}.libs")
            install(DIRECTORY "${PYTHON_STDLIB}/site-packages/${pkg}.libs"
                DESTINATION ${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages
            )
        endif()
    endforeach()
endif()
