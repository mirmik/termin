cmake_minimum_required(VERSION 3.16)
project(termin_native LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Ensure standard install dir variables (CMAKE_INSTALL_INCLUDEDIR, etc.) are set.
include(GNUInstallDirs)
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/../../cmake")
include(TerminRpath)

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

# Install prefix for Python modules only.
# Shared C/C++ runtime libraries are installed into the normal lib/bin dirs.
# For standalone: lib/python/termin/, for setup.py: CMAKE_INSTALL_PREFIX directly
if(BUILD_STANDALONE OR TERMIN_BUILD_MONOREPO)
    set(TERMIN_PYTHON_PREFIX "${CMAKE_INSTALL_PREFIX}/lib/python/termin")
    set(TERMIN_PYTHON_INSTALL_DIR "lib/python/termin")
else()
    set(TERMIN_PYTHON_PREFIX "${CMAKE_INSTALL_PREFIX}")
    set(TERMIN_PYTHON_INSTALL_DIR ".")
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
    set(CMAKE_CXX_FLAGS_DEBUG "/Zi /Od /DEBUG /FS")
    set(CMAKE_C_FLAGS_DEBUG "/Zi /Od /DEBUG /FS")
    set(CMAKE_CXX_FLAGS_RELEASE "/O2 /DNDEBUG")
    set(OPTIMIZE_FLAGS /O2 /fp:fast)
    add_compile_options(/wd4251 /wd4275)
    add_definitions(-D_CRT_SECURE_NO_WARNINGS)
else()
    set(CMAKE_CXX_FLAGS_DEBUG "-g -O0 -fno-omit-frame-pointer")
    set(CMAKE_C_FLAGS_DEBUG "-g -O0 -fno-omit-frame-pointer")
    set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG")
    set(OPTIMIZE_FLAGS -O3 -ffast-math)
endif()

find_package(Python COMPONENTS Interpreter Development REQUIRED)

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

# Core C library
if(BUILD_TESTS)
    set(TC_BUILD_TESTS ON CACHE BOOL "" FORCE)
else()
    set(TC_BUILD_TESTS OFF CACHE BOOL "" FORCE)
endif()
add_subdirectory(${TERMIN_ROOT}/core_c ${CMAKE_CURRENT_BINARY_DIR}/core_c)

# ============== Entity shared library ==============
# Must be SHARED so that singletons (ComponentRegistry, InspectRegistry, KindRegistryCpp, EntityRegistry)
# are the same instance across all Python extension modules.
set(ENTITY_LIB_SOURCES
    # Entity-related sources that remain in termin (not migrated to termin-scene)
    termin/entity/entity_registry.cpp
    termin/camera/orbit_camera_controller.cpp
    ${TERMIN_ROOT}/core_c/src/tc_inspect_component_adapter.cpp
    ${TERMIN_ROOT}/core_c/src/tc_editor_interaction_instance.cpp
)

if(NOT TC_EXTERNAL_INSPECT_ACTIVE)
    list(APPEND ENTITY_LIB_SOURCES
        ${TERMIN_ROOT}/core_c/src/tc_inspect_core_instance.cpp
        termin/inspect/tc_kind_cpp.cpp
    )
else()
    message(STATUS "entity_lib: using inspect/kind C++ core from external termin_inspect")
endif()
add_library(entity_lib SHARED ${ENTITY_LIB_SOURCES})
if(COMMAND termin_add_alias_if_missing)
    termin_add_alias_if_missing(termin::entity_lib entity_lib)
endif()
target_include_directories(entity_lib PUBLIC
    $<BUILD_INTERFACE:${TERMIN_ROOT}/core_c/include>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<BUILD_INTERFACE:${TERMIN_ROOT}/../termin-components/termin-components-render>
    $<BUILD_INTERFACE:${TERMIN_ROOT}/../termin-render/include>
    $<INSTALL_INTERFACE:include/core_c>
    $<INSTALL_INTERFACE:include/cpp>
    $<INSTALL_INTERFACE:include>
)
if(TERMIN_BUILD_PYTHON)
    find_package(nanobind CONFIG REQUIRED)
    target_link_libraries(entity_lib PUBLIC termin_core tcbase::termin_base termin_inspect::termin_inspect termin_scene::termin_scene termin_input::termin_input termin_collision::termin_collision termin_components_collision::termin_components_collision termin_components_kinematic::termin_components_kinematic termin_components_render::termin_components_render termin_render::termin_render termin_display::termin_display PRIVATE nanobind Python::Python)
    target_link_libraries(entity_lib PUBLIC termin_inspect::termin_inspect_python)
    target_compile_definitions(entity_lib PRIVATE TERMIN_HAS_NANOBIND)
else()
    target_link_libraries(entity_lib PUBLIC termin_core tcbase::termin_base termin_inspect::termin_inspect termin_scene::termin_scene termin_input::termin_input termin_collision::termin_collision termin_components_collision::termin_components_collision termin_components_kinematic::termin_components_kinematic termin_components_render::termin_components_render termin_render::termin_render termin_display::termin_display)
endif()
target_compile_definitions(entity_lib PRIVATE TERMIN_SCENE_EXPORTS ENTITY_LIB_EXPORTS TC_EXPORTS)
target_compile_options(entity_lib PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
if(COMMAND termin_enable_pch_for)
    termin_enable_pch_for(entity_lib)
else()
    target_precompile_headers(entity_lib PRIVATE termin/pch.hpp)
endif()
set_target_properties(entity_lib PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    WINDOWS_EXPORT_ALL_SYMBOLS ON
    INSTALL_RPATH "$ORIGIN;${CMAKE_INSTALL_PREFIX}/lib"
)
if(COMMAND termin_enable_unity_build_for)
    termin_enable_unity_build_for(entity_lib)
endif()

# ============== Render library ==============
# Legacy app-side render glue that still depends on RenderingManager.
set(RENDER_LIB_SOURCES
    # Render extension for TcSceneRef (uses RenderingManager)
    termin/tc_scene_render_ext.cpp
)
add_library(render_lib SHARED ${RENDER_LIB_SOURCES})
if(COMMAND termin_add_alias_if_missing)
    termin_add_alias_if_missing(termin::render_lib render_lib)
endif()
target_include_directories(render_lib PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<INSTALL_INTERFACE:include/cpp>
)
target_link_libraries(render_lib PUBLIC entity_lib tcbase::termin_base tgfx::termin_graphics tgfx::termin_graphics2 termin_materials::termin_materials termin_render::termin_render termin_render_passes::termin_render_passes termin_display::termin_display termin_components_collision::termin_components_collision termin_components_render::termin_components_render termin_engine::termin_engine)
if(TGFX2_ENABLE_OPENGL)
    target_link_libraries(render_lib PUBLIC OpenGL::GL)
endif()
target_compile_definitions(render_lib PRIVATE TERMIN_RENDER_EXPORTS)
target_compile_options(render_lib PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
if(COMMAND termin_enable_pch_for)
    termin_enable_pch_for(render_lib)
else()
    target_precompile_headers(render_lib PRIVATE termin/pch.hpp)
endif()
set_target_properties(render_lib PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    WINDOWS_EXPORT_ALL_SYMBOLS ON
    INSTALL_RPATH "$ORIGIN;${CMAKE_INSTALL_PREFIX}/lib"
)
if(COMMAND termin_enable_unity_build_for)
    termin_enable_unity_build_for(render_lib)
endif()

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
if(TERMIN_BUILD_PYTHON)
    include(${CMAKE_CURRENT_SOURCE_DIR}/python_bindings.cmake)
endif()

# ============== SDK Command Tools ==============
add_executable(termin
    app/termin.cpp
)
target_compile_features(termin PRIVATE cxx_std_20)
target_compile_options(termin PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
set_target_properties(termin PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
)
termin_set_rpath_tool(termin)
install(TARGETS termin RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})

add_executable(termin_builder
    app/termin_builder.cpp
)
target_compile_features(termin_builder PRIVATE cxx_std_20)
target_include_directories(termin_builder PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)
target_link_libraries(termin_builder PRIVATE tcbase::termin_base)
target_compile_options(termin_builder PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
set_target_properties(termin_builder PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
)
termin_set_rpath_tool(termin_builder)
install(TARGETS termin_builder RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})

add_executable(termin_runner
    app/termin_runner.cpp
)
target_compile_features(termin_runner PRIVATE cxx_std_20)
target_include_directories(termin_runner PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)
target_link_libraries(termin_runner PRIVATE tcbase::termin_base)
target_compile_options(termin_runner PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
set_target_properties(termin_runner PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
)
termin_set_rpath_tool(termin_runner)
install(TARGETS termin_runner RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})

add_executable(termin_player
    app/termin_player.cpp
)
target_compile_features(termin_player PRIVATE cxx_std_20)
target_include_directories(termin_player PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${Python_INCLUDE_DIRS}
)
target_link_libraries(termin_player PRIVATE
    Python::Python
    termin_engine::termin_engine
    termin_render::termin_render
    termin_collision::termin_collision
)
target_compile_options(termin_player PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
set_target_properties(termin_player PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
)
if(WIN32)
    set_target_properties(termin_player PROPERTIES WIN32_EXECUTABLE FALSE)
endif()
install(TARGETS termin_player RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
set_target_properties(termin_player PROPERTIES
    INSTALL_RPATH "$ORIGIN/../lib;$ORIGIN"
    BUILD_RPATH "${CMAKE_BINARY_DIR}/bin"
    BUILD_WITH_INSTALL_RPATH FALSE
)

add_executable(termin_stdlib
    app/termin_stdlib.cpp
)
target_compile_features(termin_stdlib PRIVATE cxx_std_20)
target_compile_options(termin_stdlib PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
set_target_properties(termin_stdlib PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
)
termin_set_rpath_tool(termin_stdlib)
install(TARGETS termin_stdlib RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})

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
        INSTALL_RPATH "$ORIGIN/../lib;$ORIGIN/../lib/python/termin;$ORIGIN"
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
        INSTALL_RPATH "$ORIGIN/../lib;$ORIGIN/../lib/python/termin;$ORIGIN"
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
        tests/tests_general_pose3.cpp
        tests/tests_inspect_registry.cpp
        tests/tests_orbit_camera_controller.cpp
        tests/tests_rendering_manager.cpp
        tests/tests_shader_parser_std140.cpp
    )
    target_include_directories(termin_tests PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/tests
        ${CMAKE_CURRENT_SOURCE_DIR}/../../termin-thirdparty/guard
    )
    target_link_libraries(termin_tests PRIVATE
        entity_lib
        render_lib
        termin_components_render::termin_components_render
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

# ============== Install shared libraries ==============
set(TERMIN_INSTALL_TARGETS entity_lib termin_core render_lib)
install(TARGETS ${TERMIN_INSTALL_TARGETS}
    EXPORT terminTargets
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
)

if(WIN32 AND SDL2_DLL)
    install(FILES ${SDL2_DLL} DESTINATION ${CMAKE_INSTALL_BINDIR})
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

set(TERMIN_SDK_PYTHON_PACKAGE_DIRS
    ${TERMIN_ROOT}/../termin-animation/python/termin/
    ${TERMIN_ROOT}/../termin-collision/python/termin/
    ${TERMIN_ROOT}/../termin-components/termin-components-collision/python/termin/
    ${TERMIN_ROOT}/../termin-components/termin-components-kinematic/python/termin/
    ${TERMIN_ROOT}/../termin-components/termin-components-mesh/python/termin/
    ${TERMIN_ROOT}/../termin-components/termin-components-render/python/termin/
    ${TERMIN_ROOT}/../termin-csg/python/termin/
    ${TERMIN_ROOT}/../termin-display/python/termin/
    ${TERMIN_ROOT}/../termin-engine/python/termin/
    ${TERMIN_ROOT}/../termin-input/python/termin/
    ${TERMIN_ROOT}/../termin-lighting/python/termin/
    ${TERMIN_ROOT}/../termin-navmesh/python/termin/
    ${TERMIN_ROOT}/../termin-physics/python/termin/
    ${TERMIN_ROOT}/../termin-render-passes/python/termin/
    ${TERMIN_ROOT}/../termin-render/python/termin/
    ${TERMIN_ROOT}/../termin-scene/python/termin/
    ${TERMIN_ROOT}/../termin-skeleton/python/termin/
)
foreach(package_dir IN LISTS TERMIN_SDK_PYTHON_PACKAGE_DIRS)
    if(EXISTS ${package_dir})
        install(DIRECTORY ${package_dir}
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
    endif()
endforeach()

install(DIRECTORY ${TERMIN_ROOT}/../termin-assets/termin_assets
    DESTINATION lib/python
    PATTERN "__pycache__" EXCLUDE
    PATTERN "*.pyc" EXCLUDE
    PATTERN "*.pyo" EXCLUDE
)
install(DIRECTORY ${TERMIN_ROOT}/../termin-gui/python/tcgui
    DESTINATION lib/python
    PATTERN "__pycache__" EXCLUDE
    PATTERN "*.pyc" EXCLUDE
    PATTERN "*.pyo" EXCLUDE
    PATTERN "tests" EXCLUDE
)
install(DIRECTORY ${TERMIN_ROOT}/../termin-nodegraph/python/tcnodegraph
    DESTINATION lib/python
    PATTERN "__pycache__" EXCLUDE
    PATTERN "*.pyc" EXCLUDE
    PATTERN "*.pyo" EXCLUDE
    PATTERN "tests" EXCLUDE
)

# Install headers
install(DIRECTORY ${TERMIN_ROOT}/core_c/include/
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/core_c
    FILES_MATCHING PATTERN "*.h" PATTERN "*.hpp"
)
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/termin
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/cpp
    FILES_MATCHING PATTERN "*.h" PATTERN "*.hpp"
    PATTERN "bindings" EXCLUDE
)
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
