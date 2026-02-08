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

# Enable CTest at top level so tests from subdirectories are discoverable
if(BUILD_TESTS)
    enable_testing()
endif()

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
        OUTPUT_VARIABLE PYTHON_PREFIX_RAW
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    execute_process(
        COMMAND ${Python_EXECUTABLE} -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        OUTPUT_VARIABLE PYTHON_VERSION
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )

    # Normalize path to CMake format (forward slashes)
    file(TO_CMAKE_PATH "${PYTHON_PREFIX_RAW}" PYTHON_PREFIX)

    # Platform-specific paths:
    # Linux: {prefix}/lib/python3.12/, libpython3.12.so
    # Windows: {prefix}/Lib/, python312.dll (DLL is in prefix, not lib)
    if(WIN32)
        set(PYTHON_STDLIB "${PYTHON_PREFIX}/Lib")
        set(PYTHON_SITEPACKAGES "${PYTHON_PREFIX}/Lib/site-packages")
    else()
        set(PYTHON_LIBDIR "${PYTHON_PREFIX}/lib")
        set(PYTHON_STDLIB "${PYTHON_LIBDIR}/python${PYTHON_VERSION}")
        set(PYTHON_SITEPACKAGES "${PYTHON_STDLIB}/site-packages")
    endif()

    message(STATUS "Will bundle Python ${PYTHON_VERSION} from ${PYTHON_PREFIX}")
    message(STATUS "Python stdlib: ${PYTHON_STDLIB}")

    if(NOT WIN32)
        # Linux: Install libpython shared library
        install(DIRECTORY ${PYTHON_LIBDIR}/
            DESTINATION ${CMAKE_INSTALL_PREFIX}/lib
            FILES_MATCHING
            PATTERN "libpython${PYTHON_VERSION}*.so*"
            PATTERN "python${PYTHON_VERSION}" EXCLUDE
        )
        set(STDLIB_INSTALL_DIR "${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}")
        set(SITEPACKAGES_INSTALL_DIR "${STDLIB_INSTALL_DIR}/site-packages")
    else()
        # Windows: Install python3xx.dll to bin/
        file(GLOB PYTHON_DLLS "${PYTHON_PREFIX}/python*.dll")
        install(FILES ${PYTHON_DLLS}
            DESTINATION ${CMAKE_INSTALL_PREFIX}/bin
        )
        # Windows: Install DLLs/ directory (C extension modules)
        if(EXISTS "${PYTHON_PREFIX}/DLLs")
            install(DIRECTORY "${PYTHON_PREFIX}/DLLs"
                DESTINATION ${CMAKE_INSTALL_PREFIX}
            )
        endif()
        # Windows expects stdlib in {prefix}/Lib/ (capital L, no version)
        set(STDLIB_INSTALL_DIR "${CMAKE_INSTALL_PREFIX}/Lib")
        set(SITEPACKAGES_INSTALL_DIR "${STDLIB_INSTALL_DIR}/site-packages")
    endif()

    # Install Python standard library (excluding heavy/unneeded parts)
    install(DIRECTORY ${PYTHON_STDLIB}/
        DESTINATION ${STDLIB_INSTALL_DIR}
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        PATTERN "*.pyo" EXCLUDE
        PATTERN "test" EXCLUDE
        PATTERN "tests" EXCLUDE
        PATTERN "idle_test" EXCLUDE
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
        yaml
    )

    # Install each package
    foreach(pkg ${BUNDLE_PACKAGES})
        if(EXISTS "${PYTHON_SITEPACKAGES}/${pkg}")
            install(DIRECTORY "${PYTHON_SITEPACKAGES}/${pkg}"
                DESTINATION ${SITEPACKAGES_INSTALL_DIR}
                PATTERN "__pycache__" EXCLUDE
                PATTERN "*.pyc" EXCLUDE
            )
        endif()
        # Also copy .dist-info directories
        file(GLOB DIST_INFOS "${PYTHON_SITEPACKAGES}/${pkg}*.dist-info")
        foreach(di ${DIST_INFOS})
            install(DIRECTORY ${di}
                DESTINATION ${SITEPACKAGES_INSTALL_DIR}
            )
        endforeach()
    endforeach()

    if(NOT WIN32)
        # Linux: Copy standalone .so files (like PyQt6_sip)
        file(GLOB STANDALONE_SOS "${PYTHON_SITEPACKAGES}/*.so")
        install(FILES ${STANDALONE_SOS}
            DESTINATION ${SITEPACKAGES_INSTALL_DIR}
        )
    else()
        # Windows: Copy standalone .pyd files
        file(GLOB STANDALONE_PYDS "${PYTHON_SITEPACKAGES}/*.pyd")
        install(FILES ${STANDALONE_PYDS}
            DESTINATION ${SITEPACKAGES_INSTALL_DIR}
        )
    endif()

    # Copy .libs directories (numpy.libs, scipy.libs, pillow.libs contain vendored shared libs)
    foreach(pkg numpy scipy pillow Pillow)
        if(EXISTS "${PYTHON_SITEPACKAGES}/${pkg}.libs")
            install(DIRECTORY "${PYTHON_SITEPACKAGES}/${pkg}.libs"
                DESTINATION ${SITEPACKAGES_INSTALL_DIR}
            )
        endif()
    endforeach()
endif()
