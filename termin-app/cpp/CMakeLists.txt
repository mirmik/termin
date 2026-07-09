cmake_minimum_required(VERSION 3.16)
project(termin_native LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Ensure standard install dir variables (CMAKE_INSTALL_INCLUDEDIR, etc.) are set.
include(GNUInstallDirs)
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/../../cmake")
include(TerminRpath)
include(TerminSDL2)

# Project root - either from parent CMakeLists.txt or compute from here
if(NOT DEFINED TERMIN_ROOT)
    set(TERMIN_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/..")
endif()
# Standalone build mode (C++ app with embedded Python)
option(BUILD_STANDALONE "Build as standalone C++ application" OFF)
if(BUILD_EDITOR_MINIMAL)
    set(BUILD_STANDALONE ON)
endif()

option(TERMIN_BUILD_PYTHON "Build Python/nanobind bindings" ON)

# Default to Release build for single-config generators
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

# Put all binaries into a flat bin/ directory so tests don't depend on config subdirs
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
if(CMAKE_CONFIGURATION_TYPES)
    foreach(cfg ${CMAKE_CONFIGURATION_TYPES})
        string(TOUPPER ${cfg} cfg_upper)
        set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_${cfg_upper} ${CMAKE_BINARY_DIR}/bin)
        set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_${cfg_upper} ${CMAKE_BINARY_DIR}/bin)
        set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_${cfg_upper} ${CMAKE_BINARY_DIR}/bin)
    endforeach()
endif()

# Platform-specific optimization flags
if(MSVC)
    set(CMAKE_CXX_FLAGS_DEBUG "/Zi /Od /DEBUG /FS")
    set(CMAKE_C_FLAGS_DEBUG "/Zi /Od /DEBUG /FS")
    set(CMAKE_CXX_FLAGS_RELEASE "/O2 /DNDEBUG")
    set(OPTIMIZE_FLAGS /O2 /fp:precise)
    add_compile_options(/wd4251 /wd4275)
    add_definitions(-D_CRT_SECURE_NO_WARNINGS)
else()
    set(CMAKE_CXX_FLAGS_DEBUG "-g -O0 -fno-omit-frame-pointer")
    set(CMAKE_C_FLAGS_DEBUG "-g -O0 -fno-omit-frame-pointer")
    set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG")
    set(OPTIMIZE_FLAGS -O3)
endif()

find_package(Python COMPONENTS Interpreter Development REQUIRED)

execute_process(
    COMMAND ${Python_EXECUTABLE} -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    OUTPUT_VARIABLE PYTHON_VERSION
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

# Install prefix for Python modules only.
# Shared C/C++ runtime libraries are installed into the normal lib/bin dirs.
if(BUILD_STANDALONE OR TERMIN_BUILD_MONOREPO)
    if(WIN32)
        set(TERMIN_PYTHON_INSTALL_DIR "python/Lib/site-packages/termin")
    else()
        set(TERMIN_PYTHON_INSTALL_DIR "lib/python${PYTHON_VERSION}/site-packages/termin")
    endif()
    set(TERMIN_PYTHON_PREFIX "${CMAKE_INSTALL_PREFIX}/${TERMIN_PYTHON_INSTALL_DIR}")
else()
    set(TERMIN_PYTHON_PREFIX "${CMAKE_INSTALL_PREFIX}")
    set(TERMIN_PYTHON_INSTALL_DIR ".")
endif()

set(TERMIN_HOST_PYTHON_PATHS "")
foreach(path_var Python_SITELIB Python_SITEARCH)
    if(DEFINED ${path_var} AND NOT "${${path_var}}" STREQUAL "")
        list(APPEND TERMIN_HOST_PYTHON_PATHS "${${path_var}}")
    endif()
endforeach()
list(REMOVE_DUPLICATES TERMIN_HOST_PYTHON_PATHS)
string(REPLACE "\\" "/" TERMIN_HOST_PYTHON_PATHS "${TERMIN_HOST_PYTHON_PATHS}")
string(REPLACE ";" "|" TERMIN_HOST_PYTHON_PATHS_STR "${TERMIN_HOST_PYTHON_PATHS}")

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR})

# ============== External dependencies ==============

if(TGFX2_ENABLE_OPENGL)
    find_package(OpenGL REQUIRED)
endif()

# termin-base (provides shared enums: MouseButton, Action, Mods)
if(COMMAND termin_require_package)
    termin_require_package(termin_base tcbase::termin_base)
else()
    find_package(termin_base REQUIRED)
endif()

# termin-graphics (provides tgfx types, gpu_ops, opengl backend)
if(COMMAND termin_require_package)
    termin_require_package(termin_graphics tgfx::termin_graphics tgfx::termin_graphics2)
else()
    find_package(termin_graphics REQUIRED)
endif()
# termin-materials (shader parser, GLSL preprocessor, material-format runtime)
if(COMMAND termin_require_package)
    termin_require_package(termin_materials termin_materials::termin_materials)
else()
    find_package(termin_materials REQUIRED)
endif()
# termin-inspect (extracted inspect/kind core + python bridge)
if(COMMAND termin_require_package)
    termin_require_package(termin_inspect termin_inspect::termin_inspect)
else()
    find_package(termin_inspect REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_render termin_render::termin_render)
else()
    find_package(termin_render REQUIRED)
endif()
if(TERMIN_BUILD_PYTHON AND NOT TARGET termin_inspect::termin_inspect_python)
    message(FATAL_ERROR "termin Python build requires termin_inspect::termin_inspect_python. Rebuild/install termin-inspect with TERMIN_BUILD_PYTHON=ON.")
endif()

# termin-scene (C ECS core + C++ wrappers: Entity, Component, TcSceneRef)
if(COMMAND termin_require_package)
    termin_require_package(termin_scene termin_scene::termin_scene)
else()
    find_package(termin_scene REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_input termin_input::termin_input)
else()
    find_package(termin_input REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_display termin_display::termin_display)
else()
    find_package(termin_display REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_engine termin_engine::termin_engine)
else()
    find_package(termin_engine REQUIRED)
endif()
# termin-collision (colliders + collision world)
if(COMMAND termin_require_package)
    termin_require_package(termin_collision termin_collision::termin_collision)
else()
    find_package(termin_collision REQUIRED)
endif()
# termin-components-collision (ColliderComponent)
if(COMMAND termin_require_package)
    termin_require_package(termin_components_collision termin_components_collision::termin_components_collision)
else()
    find_package(termin_components_collision REQUIRED)
endif()
# termin-components-kinematic (ActuatorComponent, RotatorComponent)
if(COMMAND termin_require_package)
    termin_require_package(termin_components_kinematic termin_components_kinematic::termin_components_kinematic)
else()
    find_package(termin_components_kinematic REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_render termin_components_render::termin_components_render)
else()
    find_package(termin_components_render REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_render_passes termin_render_passes::termin_render_passes)
else()
    find_package(termin_render_passes REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_skeleton termin_skeleton::termin_skeleton)
else()
    find_package(termin_skeleton REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_animation termin_animation::termin_animation)
else()
    find_package(termin_animation REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_voxels termin_voxels::termin_voxels)
else()
    find_package(termin_voxels REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_components_skeleton termin_components_skeleton::termin_components_skeleton)
else()
    find_package(termin_components_skeleton REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_modules termin_modules::termin_modules)
else()
    find_package(termin_modules REQUIRED)
endif()
if(COMMAND termin_require_package)
    termin_require_package(termin_navmesh termin_navmesh::termin_navmesh)
else()
    find_package(termin_navmesh REQUIRED)
endif()
if(TARGET termin_navmesh::termin_navmesh_components)
    set(TERMIN_HAS_RECAST ON)
else()
    set(TERMIN_HAS_RECAST OFF)
endif()

# ============== SDL2 (optional) ==============
option(USE_SYSTEM_SDL2 "Use native SDL2 library" ON)

termin_configure_sdl2()

# ============== Python bindings (nanobind) ==============
if(TERMIN_BUILD_PYTHON)
    include(${CMAKE_CURRENT_SOURCE_DIR}/python_bindings.cmake)
endif()

# ============== Editor Executable ==============
option(BUILD_EDITOR_MINIMAL "Build minimal termin_editor (no Qt C++ SDK required)" OFF)

if(BUILD_EDITOR_MINIMAL)
    add_executable(termin_editor
        app/main_minimal.cpp
    )
    target_include_directories(termin_editor PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${Python_INCLUDE_DIRS}
    )
    target_link_libraries(termin_editor PRIVATE
        Python::Python
        termin_engine::termin_engine
        termin_render::termin_render
        termin_collision::termin_collision
    )
    target_compile_options(termin_editor PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
    target_compile_definitions(termin_editor PRIVATE TERMIN_HOST_PYTHON_PATHS="${TERMIN_HOST_PYTHON_PATHS_STR}")
    set_target_properties(termin_editor PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
    )
    if(WIN32)
        set_target_properties(termin_editor PROPERTIES WIN32_EXECUTABLE FALSE)
    endif()
    install(TARGETS termin_editor RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
    set_target_properties(termin_editor PROPERTIES
        INSTALL_RPATH "$ORIGIN/../lib;$ORIGIN"
        BUILD_RPATH "${CMAKE_BINARY_DIR}/bin"
        BUILD_WITH_INSTALL_RPATH FALSE
    )
endif()

# ============== Launcher Test Executable ==============
option(BUILD_LAUNCHER "Build termin_launcher (UIRenderer test, no Qt)" OFF)

if(BUILD_LAUNCHER)
    add_executable(termin_launcher
        app/main_launcher.cpp
    )
    target_include_directories(termin_launcher PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${Python_INCLUDE_DIRS}
    )
    target_link_libraries(termin_launcher PRIVATE Python::Python)
    target_compile_options(termin_launcher PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
    target_compile_definitions(termin_launcher PRIVATE TERMIN_HOST_PYTHON_PATHS="${TERMIN_HOST_PYTHON_PATHS_STR}")
    set_target_properties(termin_launcher PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
    )
    if(WIN32)
        set_target_properties(termin_launcher PROPERTIES WIN32_EXECUTABLE FALSE)
    endif()
    install(TARGETS termin_launcher RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
    set_target_properties(termin_launcher PROPERTIES
        INSTALL_RPATH "$ORIGIN/../lib;$ORIGIN"
        BUILD_RPATH "${CMAKE_BINARY_DIR}/bin"
        BUILD_WITH_INSTALL_RPATH FALSE
    )
endif()

# ============== Tests ==============
option(BUILD_TESTS "Build C++ tests" OFF)

if(BUILD_TESTS)
    enable_testing()

    set(DEFAULT_CTEST_CONFIG "Debug")
    configure_file(
        ${CMAKE_CURRENT_SOURCE_DIR}/CTestCustom.cmake.in
        ${CMAKE_CURRENT_BINARY_DIR}/CTestCustom.cmake
        @ONLY
    )

    add_executable(termin_tests
        tests/main.cpp
        termin/editor/component_editor_visual.cpp
        termin/editor/camera_frustum_debug_gizmo.cpp
        termin/editor/editor_interaction_system.cpp
        termin/editor/editor_snap.cpp
        termin/editor/gizmo_manager.cpp
        termin/editor/camera_frustum_math.cpp
        termin/editor/transform_gizmo.cpp
        termin/render/solid_primitive_renderer.cpp
        tests/tests_general_pose3.cpp
        tests/tests_editor_interaction_system.cpp
        tests/tests_inspect_registry.cpp
        tests/tests_orbit_camera_controller.cpp
        tests/tests_camera_frustum_debug_gizmo.cpp
        tests/tests_rendering_manager.cpp
        tests/tests_shader_parser_std140.cpp
    )
    target_include_directories(termin_tests PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/tests
        ${CMAKE_CURRENT_SOURCE_DIR}/../../termin-thirdparty/guard
    )
    target_link_libraries(termin_tests PRIVATE
        tcbase::termin_base
        termin_inspect::termin_inspect
        termin_scene::termin_scene
        termin_input::termin_input
        termin_engine::termin_engine
        termin_components_render::termin_components_render
        termin_components_collision::termin_components_collision
        termin_components_kinematic::termin_components_kinematic
        termin_collision::termin_collision
        termin_render::termin_render
        termin_render_passes::termin_render_passes
        tgfx::termin_graphics
        tgfx::termin_graphics2
        ${CMAKE_DL_LIBS}
    )
    target_compile_options(termin_tests PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
    add_test(NAME termin_tests COMMAND ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin_tests${CMAKE_EXECUTABLE_SUFFIX})

    add_custom_target(termin_run_tests
        COMMAND ${CMAKE_CTEST_COMMAND} --output-on-failure -C $<CONFIG>
        DEPENDS termin_tests
        WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
        COMMENT "Running C++ tests")
endif()

if(WIN32 AND SDL2_DLL)
    termin_install_sdl2_runtime(${CMAKE_INSTALL_BINDIR})
endif()

# Install termin-app Python sources (editor, launcher, project tooling, facades).
# Native modules and extracted subproject packages install their own files into
# the same namespace; this adds the app-level Python modules they do not own.
install(DIRECTORY ${TERMIN_ROOT}/termin/
    DESTINATION ${TERMIN_PYTHON_INSTALL_DIR}
    PATTERN "__pycache__" EXCLUDE
    PATTERN "*.pyc" EXCLUDE
    PATTERN "*.pyo" EXCLUDE
    PATTERN "*.so" EXCLUDE
    PATTERN "*.dll" EXCLUDE
    PATTERN "*.dylib" EXCLUDE
    PATTERN "*.egg-info" EXCLUDE
    PATTERN "tests" EXCLUDE
    PATTERN "include" EXCLUDE
)

install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/termin
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/cpp
    FILES_MATCHING PATTERN "*.h" PATTERN "*.hpp"
    PATTERN "bindings" EXCLUDE
)
