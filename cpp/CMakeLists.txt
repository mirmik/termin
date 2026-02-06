cmake_minimum_required(VERSION 3.16)
project(termin_native LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Ensure standard install dir variables (CMAKE_INSTALL_INCLUDEDIR, etc.) are set.
include(GNUInstallDirs)

# Project root - either from parent CMakeLists.txt or compute from here
if(NOT DEFINED TERMIN_ROOT)
    set(TERMIN_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/..")
endif()

# Standalone build mode (C++ app with embedded Python)
option(BUILD_STANDALONE "Build as standalone C++ application" OFF)
if(BUILD_EDITOR_MINIMAL OR BUILD_EDITOR_EXE)
    set(BUILD_STANDALONE ON)
endif()

# C# SWIG bindings option (must be declared early to skip nanobind when ON)
option(BUILD_CSHARP_BINDINGS "Build C# SWIG bindings (termin.dll)" OFF)

# Install prefix for Python modules
# For standalone: lib/python/termin/, for setup.py: CMAKE_INSTALL_PREFIX directly
if(BUILD_STANDALONE)
    set(TERMIN_PYTHON_PREFIX "${CMAKE_INSTALL_PREFIX}/lib/python/termin")
else()
    set(TERMIN_PYTHON_PREFIX "${CMAKE_INSTALL_PREFIX}")
endif()

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
    set(CMAKE_CXX_FLAGS_DEBUG "/Zi /Od /DEBUG")
    set(CMAKE_C_FLAGS_DEBUG "/Zi /Od /DEBUG")
    set(CMAKE_CXX_FLAGS_RELEASE "/O2 /DNDEBUG")
    set(OPTIMIZE_FLAGS /O2 /fp:fast)
else()
    set(CMAKE_CXX_FLAGS_DEBUG "-g -O0 -fno-omit-frame-pointer")
    set(CMAKE_C_FLAGS_DEBUG "-g -O0 -fno-omit-frame-pointer")
    set(CMAKE_CXX_FLAGS_RELEASE "-O3 -march=native -DNDEBUG")
    set(OPTIMIZE_FLAGS -O3 -march=native -ffast-math)
endif()

find_package(Python COMPONENTS Interpreter Development REQUIRED)

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR})

# ============== Trent library ==============
# trent library - STATIC on Windows (avoids DLL import library issues), SHARED on Linux
if(WIN32)
    add_library(trent STATIC
        trent/trent.cpp
        trent/trent_path.cpp
        trent/string_ext.cpp
        trent/yaml.cpp
        trent/json.cpp
    )
else()
    add_library(trent SHARED
        trent/trent.cpp
        trent/trent_path.cpp
        trent/string_ext.cpp
        trent/yaml.cpp
        trent/json.cpp
    )
endif()
target_compile_options(trent PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
set_target_properties(trent PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
    ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${CMAKE_BINARY_DIR}/bin
    ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_BINARY_DIR}/bin
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
    LIBRARY_OUTPUT_DIRECTORY_DEBUG ${CMAKE_BINARY_DIR}/bin
    LIBRARY_OUTPUT_DIRECTORY_RELEASE ${CMAKE_BINARY_DIR}/bin
)

# ============== External dependencies ==============

# Find OpenGL
find_package(OpenGL REQUIRED)

# Disable optimizations for glad.c (large file, slow to compile with -O2)
set_source_files_properties(
    termin/render/glad/src/glad.c
    PROPERTIES COMPILE_OPTIONS "-O0"
)

# Core C library
set(TC_BUILD_TESTS OFF CACHE BOOL "" FORCE)
add_subdirectory(${TERMIN_ROOT}/core_c ${CMAKE_CURRENT_BINARY_DIR}/core_c)

# Recast library only (from recastnavigation, avoids configure_file race conditions)
set(SOVERSION 1)
set(LIB_VERSION 1.6.0)
set(RECASTNAVIGATION_ENABLE_ASSERTS OFF)
set(SKIP_INSTALL_ALL ON)  # Don't use recast's own install rules
add_subdirectory(${TERMIN_ROOT}/third/recastnavigation/Recast ${CMAKE_CURRENT_BINARY_DIR}/Recast EXCLUDE_FROM_ALL)

# Re-add Recast to build (EXCLUDE_FROM_ALL removed it from default)
set_target_properties(Recast PROPERTIES EXCLUDE_FROM_ALL FALSE)

# Add INSTALL_INTERFACE to Recast includes for proper export
target_include_directories(Recast PUBLIC
    $<INSTALL_INTERFACE:include/recastnavigation>
)

# ============== Entity shared library ==============
# Must be SHARED so that singletons (ComponentRegistry, InspectRegistry, EntityRegistry)
# are the same instance across all Python extension modules.
set(ENTITY_LIB_SOURCES
    termin/entity/entity.cpp
    termin/entity/entity_registry.cpp
    termin/entity/component.cpp
    termin/entity/component_registry.cpp
    termin/entity/unknown_component.cpp
    termin/entity/vtable_utils.cpp
    termin/entity/input_handler.cpp
    termin/camera/camera_component.cpp
    termin/camera/orbit_camera_controller.cpp
    termin/colliders/collider_component.cpp
    termin/kinematic/rotator_component.cpp
    termin/kinematic/actuator_component.cpp
    termin/lighting/light_component.cpp
    termin/geom/general_transform3.cpp
    termin/viewport_config.cpp
    termin/tc_collision_c_api.cpp
    termin/collision/collision_world_c.cpp
    ${TERMIN_ROOT}/core_c/src/tc_inspect_instance.cpp
    ${TERMIN_ROOT}/core_c/src/tc_rendering_manager_instance.cpp
    ${TERMIN_ROOT}/core_c/src/tc_engine_core_instance.cpp
    ${TERMIN_ROOT}/core_c/src/tc_scene_manager_instance.cpp
    ${TERMIN_ROOT}/core_c/src/tc_editor_interaction_instance.cpp
    termin/inspect/tc_kind_cpp.cpp
    termin/modules/module_loader.cpp
    termin/render/tc_value_trent.cpp
)
# Python-specific sources (require nanobind)
if(NOT BUILD_CSHARP_BINDINGS)
    list(APPEND ENTITY_LIB_SOURCES
        termin/bindings/inspect/tc_kind_python_instance.cpp
        termin/bindings/inspect/tc_inspect_python.cpp
    )
endif()
add_library(entity_lib SHARED ${ENTITY_LIB_SOURCES})
target_include_directories(entity_lib PUBLIC
    $<BUILD_INTERFACE:${TERMIN_ROOT}/core_c/include>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<INSTALL_INTERFACE:include/core_c>
    $<INSTALL_INTERFACE:include/cpp>
    $<INSTALL_INTERFACE:include>
)
if(BUILD_CSHARP_BINDINGS)
    target_link_libraries(entity_lib PUBLIC termin_core PRIVATE trent)
else()
    # Find nanobind for entity_lib linking
    if(WIN32)
        execute_process(
            COMMAND python -m nanobind --cmake_dir
            OUTPUT_VARIABLE nanobind_DIR
            OUTPUT_STRIP_TRAILING_WHITESPACE
        )
    else()
        execute_process(
            COMMAND python3 -m nanobind --cmake_dir
            OUTPUT_VARIABLE nanobind_DIR
            OUTPUT_STRIP_TRAILING_WHITESPACE
        )
    endif()
    find_package(nanobind CONFIG REQUIRED)
    target_link_libraries(entity_lib PUBLIC termin_core PRIVATE trent nanobind-static Python::Python)
    target_compile_definitions(entity_lib PRIVATE TERMIN_HAS_NANOBIND)
endif()
target_compile_definitions(entity_lib PRIVATE ENTITY_LIB_EXPORTS TC_EXPORTS)
target_compile_options(entity_lib PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
target_precompile_headers(entity_lib PRIVATE termin/pch.hpp)
set_target_properties(entity_lib PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    WINDOWS_EXPORT_ALL_SYMBOLS ON
)

# ============== Skeleton library ==============
add_library(skeleton_lib STATIC
    termin/skeleton/skeleton_instance.cpp
    termin/render/skeleton_controller.cpp
)
target_link_libraries(skeleton_lib PUBLIC entity_lib PRIVATE trent)
target_compile_options(skeleton_lib PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
target_precompile_headers(skeleton_lib PRIVATE termin/pch.hpp)
set_target_properties(skeleton_lib PROPERTIES
    POSITION_INDEPENDENT_CODE ON
)

# ============== Animation library ==============
add_library(animation_lib STATIC
    termin/animation/animation_player.cpp
)
target_include_directories(animation_lib PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<INSTALL_INTERFACE:include/cpp>
)
target_link_libraries(animation_lib PUBLIC skeleton_lib)
target_compile_options(animation_lib PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
target_precompile_headers(animation_lib PRIVATE termin/pch.hpp)
set_target_properties(animation_lib PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

# ============== Render library ==============
# Includes passes with TC_REGISTER_FRAME_PASS for static registration
# SHARED for Python (consistent RTTI), STATIC for C# (WHOLEARCHIVE needs static lib)
set(RENDER_LIB_SOURCES
    termin/render/drawable.cpp
    termin/render/mesh_renderer.cpp
    termin/render/frame_pass.cpp
    termin/render/fbo_pool.cpp
    termin/render/render_engine.cpp
    termin/render/render_pipeline.cpp
    termin/render/rendering_manager.cpp
    termin/scene/scene_manager.cpp
    termin/render/pull_rendering_manager.cpp
    termin/render/wireframe_renderer.cpp
    termin/render/color_pass.cpp
    termin/render/collider_gizmo_pass.cpp
    termin/render/present_pass.cpp
    termin/render/depth_pass.cpp
    termin/render/normal_pass.cpp
    termin/render/shadow_pass.cpp
    termin/render/id_pass.cpp
    termin/render/material_pass.cpp
    termin/render/bloom_pass.cpp
    termin/render/grayscale_pass.cpp
    termin/render/tonemap_pass.cpp
    termin/render/shader_parser.cpp
    termin/render/shadow_camera.cpp
    termin/render/glsl_preprocessor.cpp
    termin/render/shader_skinning.cpp
    termin/render/graph_data.cpp
    termin/render/graph_compiler.cpp
    termin/render/scene_pipeline_template.cpp
    termin/render/tc_pass_ref.cpp
    termin/lighting/shadow.cpp
    termin/texture/tc_texture_handle.cpp
    termin/render/opengl/opengl_backend.cpp
    termin/render/opengl/opengl_backend_singleton.cpp
    termin/render/opengl/opengl_framebuffer.cpp
    termin/render/glad/src/glad.c
)
if(BUILD_CSHARP_BINDINGS)
    add_library(render_lib STATIC ${RENDER_LIB_SOURCES})
else()
    add_library(render_lib SHARED ${RENDER_LIB_SOURCES})
endif()
target_include_directories(render_lib PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<INSTALL_INTERFACE:include/cpp>
)
target_include_directories(render_lib PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/termin/render/glad/include
)
target_link_libraries(render_lib PUBLIC entity_lib trent OpenGL::GL)
if(WIN32)
    # GLAD export macros for Windows DLL
    target_compile_definitions(render_lib
        PRIVATE GLAD_API_CALL_EXPORT GLAD_API_CALL_EXPORT_BUILD RENDER_LIB_EXPORTS
        PUBLIC GLAD_API_CALL_EXPORT
    )
endif()
target_compile_options(render_lib PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
target_precompile_headers(render_lib PRIVATE termin/pch.hpp)
set_target_properties(render_lib PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    WINDOWS_EXPORT_ALL_SYMBOLS ON
)

# ============== Engine library ==============
# Core engine runtime - owns SceneManager and RenderingManager
add_library(engine_lib SHARED
    termin/engine/engine_core.cpp
)
target_include_directories(engine_lib PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<INSTALL_INTERFACE:include/cpp>
)
target_link_libraries(engine_lib PUBLIC render_lib)
target_compile_options(engine_lib PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
target_precompile_headers(engine_lib PRIVATE termin/pch.hpp)
set_target_properties(engine_lib PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    WINDOWS_EXPORT_ALL_SYMBOLS ON
)

# ============== NavMesh library ==============
# STATIC for C# (to avoid PCH symbol conflicts), SHARED for Python
if(BUILD_CSHARP_BINDINGS)
    add_library(navmesh_lib STATIC
        termin/navmesh/recast_navmesh_builder_component.cpp
    )
else()
    add_library(navmesh_lib SHARED
        termin/navmesh/recast_navmesh_builder_component.cpp
    )
endif()
target_include_directories(navmesh_lib PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<INSTALL_INTERFACE:include/cpp>
)
target_link_libraries(navmesh_lib PUBLIC entity_lib render_lib Recast)
target_compile_options(navmesh_lib PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
target_precompile_headers(navmesh_lib PRIVATE termin/pch.hpp)
set_target_properties(navmesh_lib PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    WINDOWS_EXPORT_ALL_SYMBOLS ON
)

# ============== SDL2 (optional) ==============
option(USE_SYSTEM_SDL2 "Use system SDL2 library (disable to use pysdl2)" ON)

if(USE_SYSTEM_SDL2)
    if(WIN32)
        set(SDL2_SEARCH_PATHS
            "C:/SDL2"
            "$ENV{SDL2_DIR}"
            "$ENV{PROGRAMFILES}/SDL2"
        )
        find_path(SDL2_INCLUDE_DIRS SDL2/SDL.h
            PATH_SUFFIXES include
            PATHS ${SDL2_SEARCH_PATHS}
        )
        find_library(SDL2_LIBRARY
            NAMES SDL2
            PATH_SUFFIXES lib/x64 lib
            PATHS ${SDL2_SEARCH_PATHS}
        )
        find_library(SDL2MAIN_LIBRARY
            NAMES SDL2main
            PATH_SUFFIXES lib/x64 lib
            PATHS ${SDL2_SEARCH_PATHS}
        )
        if(SDL2_INCLUDE_DIRS AND SDL2_LIBRARY)
            set(SDL2_FOUND TRUE)
            set(SDL2_LIBRARIES ${SDL2_LIBRARY})
            if(SDL2MAIN_LIBRARY)
                list(APPEND SDL2_LIBRARIES ${SDL2MAIN_LIBRARY})
            endif()
            get_filename_component(SDL2_LIB_DIR ${SDL2_LIBRARY} DIRECTORY)
            find_file(SDL2_DLL
                NAMES SDL2.dll
                PATHS ${SDL2_LIB_DIR} ${SDL2_LIB_DIR}/../bin ${SDL2_LIB_DIR}/..
                NO_DEFAULT_PATH
            )
            message(STATUS "Found SDL2: ${SDL2_INCLUDE_DIRS}")
            message(STATUS "SDL2 DLL: ${SDL2_DLL}")
        else()
            message(STATUS "SDL2 not found, disabling SDL2 support (use pysdl2 instead)")
            set(SDL2_FOUND FALSE)
        endif()
    else()
        find_package(SDL2 QUIET)
        if(NOT SDL2_FOUND)
            find_package(PkgConfig REQUIRED)
            pkg_check_modules(SDL2 REQUIRED sdl2)
        endif()
    endif()
else()
    set(SDL2_FOUND FALSE)
    message(STATUS "System SDL2 disabled, using pysdl2")
endif()

# ============== Python bindings (nanobind) ==============
if(NOT BUILD_CSHARP_BINDINGS)
    include(${CMAKE_CURRENT_SOURCE_DIR}/python_bindings.cmake)
endif()

# ============== Editor Executable ==============
option(BUILD_EDITOR_EXE "Build termin_editor executable with embedded Python" OFF)
option(BUILD_EDITOR_MINIMAL "Build minimal termin_editor (no Qt C++ SDK required)" OFF)

if(BUILD_EDITOR_MINIMAL)
    add_executable(termin_editor
        app/main_minimal.cpp
    )
    target_include_directories(termin_editor PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${Python_INCLUDE_DIRS}
    )
    target_link_libraries(termin_editor PRIVATE Python::Python engine_lib)
    target_compile_options(termin_editor PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
    set_target_properties(termin_editor PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
    )
    if(WIN32)
        set_target_properties(termin_editor PROPERTIES WIN32_EXECUTABLE FALSE)
    endif()
    install(TARGETS termin_editor RUNTIME DESTINATION ${CMAKE_INSTALL_PREFIX}/bin)
    set_target_properties(termin_editor PROPERTIES
        INSTALL_RPATH "$ORIGIN/../lib/python/termin;$ORIGIN"
        BUILD_RPATH "${CMAKE_BINARY_DIR}/bin"
        BUILD_WITH_INSTALL_RPATH FALSE
    )
endif()

if(BUILD_EDITOR_EXE)
    find_package(Qt6 COMPONENTS Widgets QUIET)
    if(NOT Qt6_FOUND)
        message(STATUS "Qt6 not found, trying Qt5...")
        find_package(Qt5 COMPONENTS Widgets REQUIRED)
        set(QT_LIBS Qt5::Widgets)
    else()
        set(QT_LIBS Qt6::Widgets)
    endif()

    add_executable(termin_editor_qt
        app/main.cpp
    )
    target_include_directories(termin_editor_qt PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${Python_INCLUDE_DIRS}
    )
    target_link_libraries(termin_editor_qt PRIVATE
        ${QT_LIBS}
        Python::Python
        entity_lib
        render_lib
        ${SDL2_LIBRARIES}
    )
    target_compile_options(termin_editor_qt PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
    set_target_properties(termin_editor_qt PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
        INSTALL_RPATH "$ORIGIN"
        BUILD_WITH_INSTALL_RPATH TRUE
    )
    if(WIN32)
        set_target_properties(termin_editor_qt PROPERTIES WIN32_EXECUTABLE FALSE)
    endif()
    install(TARGETS termin_editor_qt RUNTIME DESTINATION ${CMAKE_INSTALL_PREFIX})
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
        tests/tests_general_pose3.cpp
        tests/tests_colliders.cpp
        tests/tests_collision.cpp
    )
    target_include_directories(termin_tests PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/tests
    )
    target_link_libraries(termin_tests PRIVATE entity_lib)
    target_compile_options(termin_tests PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
    add_test(NAME termin_tests COMMAND ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin_tests${CMAKE_EXECUTABLE_SUFFIX})

    add_custom_target(run_tests
        COMMAND ${CMAKE_CTEST_COMMAND} --output-on-failure -C $<CONFIG>
        DEPENDS termin_tests
        WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
        COMMENT "Running C++ tests")
endif()

# ============== Install shared libraries ==============
install(TARGETS trent entity_lib termin_core render_lib engine_lib navmesh_lib Recast
    EXPORT terminTargets
    RUNTIME DESTINATION ${TERMIN_PYTHON_PREFIX}
    LIBRARY DESTINATION ${TERMIN_PYTHON_PREFIX}
    ARCHIVE DESTINATION ${TERMIN_PYTHON_PREFIX}/lib
)

if(WIN32 AND SDL2_DLL)
    install(FILES ${SDL2_DLL} DESTINATION ${TERMIN_PYTHON_PREFIX})
endif()

install(TARGETS skeleton_lib animation_lib
    EXPORT terminTargets
    ARCHIVE DESTINATION ${CMAKE_INSTALL_PREFIX}/lib
)

# Install headers
install(DIRECTORY ${TERMIN_ROOT}/core_c/include/
    DESTINATION ${CMAKE_INSTALL_PREFIX}/include/core_c
    FILES_MATCHING PATTERN "*.h" PATTERN "*.hpp"
)
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/termin
    DESTINATION ${CMAKE_INSTALL_PREFIX}/include/cpp
    FILES_MATCHING PATTERN "*.h" PATTERN "*.hpp"
    PATTERN "bindings" EXCLUDE
    PATTERN "render/glad" EXCLUDE
)
install(DIRECTORY ${TERMIN_ROOT}/third/recastnavigation/Recast/Include/
    DESTINATION ${CMAKE_INSTALL_PREFIX}/include/recastnavigation
    FILES_MATCHING PATTERN "*.h"
)
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/trent
    DESTINATION ${CMAKE_INSTALL_PREFIX}/include
    FILES_MATCHING PATTERN "*.h" PATTERN "*.hpp"
)

# ============== C# SWIG Bindings ==============
if(BUILD_CSHARP_BINDINGS)
    add_library(termin SHARED
        ${TERMIN_ROOT}/csharp/termin_wrap.cxx
        termin/render/opengl/tc_opengl.cpp
    )
    target_include_directories(termin PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${TERMIN_ROOT}/core_c/include
        ${CMAKE_CURRENT_SOURCE_DIR}/termin/render/glad/include
    )
    add_dependencies(termin render_lib)
    if(MSVC)
        target_link_libraries(termin PRIVATE
            OpenGL::GL
            termin_core
            trent
            entity_lib
            -WHOLEARCHIVE:$<TARGET_LINKER_FILE:render_lib>
        )
    else()
        target_link_libraries(termin PRIVATE
            OpenGL::GL
            termin_core
            trent
            entity_lib
            -Wl,--whole-archive render_lib -Wl,--no-whole-archive
        )
    endif()
    target_compile_definitions(termin PRIVATE SWIG_CSHARP TC_EXPORTS)
    if(WIN32)
        set_target_properties(termin PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)
    endif()
    target_compile_options(termin PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
    install(TARGETS termin
        RUNTIME DESTINATION ${TERMIN_ROOT}/csharp/Termin.Native/runtimes/win-x64/native
        LIBRARY DESTINATION ${TERMIN_ROOT}/csharp/Termin.Native/runtimes/linux-x64/native
    )
endif()

# ============== CMake Package Export ==============
include(CMakePackageConfigHelpers)

install(EXPORT terminTargets
    FILE terminTargets.cmake
    NAMESPACE termin::
    DESTINATION lib/cmake/termin
)

configure_package_config_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake/terminConfig.cmake.in"
    "${CMAKE_CURRENT_BINARY_DIR}/terminConfig.cmake"
    INSTALL_DESTINATION lib/cmake/termin
)

write_basic_package_version_file(
    "${CMAKE_CURRENT_BINARY_DIR}/terminConfigVersion.cmake"
    VERSION 1.0.0
    COMPATIBILITY SameMajorVersion
)

install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/terminConfig.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/terminConfigVersion.cmake"
    DESTINATION lib/cmake/termin
)
