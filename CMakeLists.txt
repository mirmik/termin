cmake_minimum_required(VERSION 3.19)
project(termin_monorepo VERSION 0.1.0 LANGUAGES C CXX)
include(CMakePackageConfigHelpers)
option(TERMIN_BUILD_MONOREPO "Build Termin as one CMake target graph" ON)
option(TERMIN_PLATFORM_ANDROID "Build Termin native runtime for Android" OFF)
option(TERMIN_PLATFORM_WEB "Build the portable Termin WebAssembly core" OFF)
option(TERMIN_ENABLE_OPENGL "Enable desktop OpenGL-dependent graphics/render targets" ON)
option(TERMIN_ENABLE_WEBGL2 "Enable the WebGL 2 constrained-GL backend" ${TERMIN_PLATFORM_WEB})
option(TERMIN_BUILD_PYTHON "Build Python/nanobind bindings" OFF)
option(TERMIN_RELOCATABLE_PYTHON_WHEELS
    "Use prefix-independent RPATHs for the standalone Python wheel product"
    OFF)
option(TERMIN_BUILD_TESTS "Build C/C++ tests" OFF)
option(TERMIN_BUILD_TGFX2_TESTS "Build tgfx2 C/C++ tests" ON)
option(TERMIN_BUILD_WINDOW_TESTS "Build tests that require a windowing system" OFF)
option(TERMIN_ENABLE_VULKAN "Enable Vulkan support" ON)
option(TERMIN_ENABLE_SDL "Enable SDL support" ON)
option(TERMIN_BUILD_EDITOR_MINIMAL "Build minimal editor executable" OFF)
option(TERMIN_BUILD_LAUNCHER "Build launcher executable" OFF)
option(TERMIN_USE_CCACHE "Use ccache as C/C++ compiler launcher when available" ON)
option(TERMIN_ENABLE_UNITY_BUILD "Enable CMake unity build for faster clean builds" OFF)
option(TERMIN_ENABLE_PCH "Enable precompiled headers for selected C++ targets" ON)
set(TERMIN_SDK_PROFILE "full" CACHE STRING
    "SDK target graph profile: full, graphics, or core")
set_property(CACHE TERMIN_SDK_PROFILE PROPERTY STRINGS full graphics core)

if(NOT TERMIN_SDK_PROFILE STREQUAL "full"
   AND NOT TERMIN_SDK_PROFILE STREQUAL "graphics"
   AND NOT TERMIN_SDK_PROFILE STREQUAL "core")
    message(FATAL_ERROR
        "Unsupported TERMIN_SDK_PROFILE='${TERMIN_SDK_PROFILE}'. "
        "Expected one of: full, graphics, core")
endif()

if(TERMIN_SDK_PROFILE STREQUAL "graphics"
   OR TERMIN_SDK_PROFILE STREQUAL "core")
    if(TERMIN_PLATFORM_ANDROID OR TERMIN_PLATFORM_WEB)
        message(FATAL_ERROR
            "TERMIN_SDK_PROFILE=${TERMIN_SDK_PROFILE} is a desktop SDK profile")
    endif()
endif()

if(TERMIN_PLATFORM_ANDROID AND TERMIN_PLATFORM_WEB)
    message(FATAL_ERROR "TERMIN_PLATFORM_ANDROID and TERMIN_PLATFORM_WEB are mutually exclusive")
endif()

if(TERMIN_PLATFORM_WEB)
    if(NOT EMSCRIPTEN)
        message(FATAL_ERROR
            "TERMIN_PLATFORM_WEB requires the Emscripten toolchain. "
            "Configure it through 'task build:web -- ...'.")
    endif()
    # The Web runtime is one statically linked Wasm module.  Newer CMake
    # versions otherwise permit Emscripten side modules for explicit SHARED
    # targets, leaving transitive engine DLL dependencies unresolved when the
    # final module is linked.
    set(BUILD_SHARED_LIBS OFF CACHE BOOL "Build shared libraries" FORCE)
    set_property(GLOBAL PROPERTY TARGET_SUPPORTS_SHARED_LIBS FALSE)
    set(TERMIN_BUILD_PYTHON OFF CACHE BOOL "Build Python/nanobind bindings" FORCE)
    set(TERMIN_BUILD_TESTS OFF CACHE BOOL "Build C/C++ tests" FORCE)
    set(TERMIN_BUILD_EDITOR_MINIMAL OFF CACHE BOOL "Build minimal editor executable" FORCE)
    set(TERMIN_BUILD_LAUNCHER OFF CACHE BOOL "Build launcher executable" FORCE)
    set(TERMIN_ENABLE_PCH OFF CACHE BOOL "Enable precompiled headers for selected targets" FORCE)
    set(TERMIN_BASE_BUILD_SHARED OFF CACHE BOOL "Build termin-base as a shared library" FORCE)
    set(TI_BUILD_SHARED OFF CACHE BOOL "Build termin-inspect as a shared library" FORCE)
    set(TERMIN_SCENE_BUILD_SHARED OFF CACHE BOOL "Build termin-scene as a shared library" FORCE)
    message(STATUS "Termin: WebAssembly core profile enabled")
elseif(TERMIN_PLATFORM_ANDROID)
    set(TERMIN_BUILD_PYTHON OFF CACHE BOOL "Build Python/nanobind bindings" FORCE)
    set(TERMIN_BUILD_TESTS OFF CACHE BOOL "Build C/C++ tests" FORCE)
    set(TERMIN_BUILD_EDITOR_MINIMAL OFF CACHE BOOL "Build minimal editor executable" FORCE)
    set(TERMIN_BUILD_LAUNCHER OFF CACHE BOOL "Build launcher executable" FORCE)
    set(TERMIN_ENABLE_PCH OFF CACHE BOOL "Enable precompiled headers for selected C++ targets" FORCE)
    message(STATUS "Termin: Android native render profile enabled")
endif()

if(TERMIN_USE_CCACHE AND NOT MSVC)
    find_program(TERMIN_CCACHE_PROGRAM ccache)
    if(TERMIN_CCACHE_PROGRAM)
        if(NOT CMAKE_C_COMPILER_LAUNCHER)
            set(CMAKE_C_COMPILER_LAUNCHER "${TERMIN_CCACHE_PROGRAM}" CACHE STRING "C compiler launcher" FORCE)
        endif()
        if(NOT CMAKE_CXX_COMPILER_LAUNCHER)
            set(CMAKE_CXX_COMPILER_LAUNCHER "${TERMIN_CCACHE_PROGRAM}" CACHE STRING "CXX compiler launcher" FORCE)
        endif()
        message(STATUS "Termin: using ccache compiler launcher: ${TERMIN_CCACHE_PROGRAM}")
    else()
        message(STATUS "Termin: ccache requested but not found")
    endif()
endif()

function(termin_enable_unity_build_for target)
    if(TERMIN_ENABLE_UNITY_BUILD AND TARGET "${target}")
        set_target_properties("${target}" PROPERTIES
            UNITY_BUILD ON
            UNITY_BUILD_BATCH_SIZE 8
        )
    endif()
endfunction()

function(termin_enable_pch_for target)
    if(TERMIN_ENABLE_PCH AND TARGET "${target}")
        get_target_property(_termin_target_type "${target}" TYPE)
        if(MSVC AND _termin_target_type STREQUAL "SHARED_LIBRARY")
            message(STATUS "Termin: PCH skipped for MSVC shared library target ${target}")
            return()
        endif()
        target_precompile_headers("${target}" PRIVATE
            "$<$<COMPILE_LANGUAGE:CXX>:${CMAKE_CURRENT_FUNCTION_LIST_DIR}/cmake/termin_cpp_pch.hpp>"
        )
    endif()
endfunction()

include(${CMAKE_CURRENT_SOURCE_DIR}/cmake/TerminTestMetadata.cmake)

if(TERMIN_ENABLE_UNITY_BUILD)
    message(STATUS "Termin: unity build enabled for selected targets")
endif()

if(TERMIN_ENABLE_PCH)
    message(STATUS "Termin: precompiled headers enabled for selected targets")
endif()

configure_package_config_file(
    cmake/terminConfig.cmake.in
    "${CMAKE_CURRENT_BINARY_DIR}/terminConfig.cmake"
    INSTALL_DESTINATION lib/cmake/termin
)
write_basic_package_version_file(
    "${CMAKE_CURRENT_BINARY_DIR}/terminConfigVersion.cmake"
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)
install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/terminConfig.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/terminConfigVersion.cmake"
    DESTINATION lib/cmake/termin
)

if(TERMIN_BUILD_TESTS)
    if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/termin-thirdparty/guard/guard_c.h"
       OR NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/termin-thirdparty/guard/guard_main.h")
        message(FATAL_ERROR
            "TERMIN_BUILD_TESTS=ON requires the guard test framework submodule. "
            "Run: git submodule update --init termin-thirdparty/guard")
    endif()
    enable_testing()
endif()

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(TerminDependencies)
include(TerminRpath)

if(TERMIN_BUILD_PYTHON)
    include(TerminPython)
    termin_require_canonical_python(Interpreter Development)
endif()

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")

add_subdirectory(core)

# Core configures its own bindings inside core/'s CMake directory scope. The
# canonical profile is included once more here so its nanobind_add_module()
# contract is also visible to bindings owned by later districts.
if(TERMIN_BUILD_PYTHON)
    include(core/termin-nanobind-sdk/cmake/TerminNanobindProfile.cmake)
endif()

if(TERMIN_SDK_PROFILE STREQUAL "core")
    message(STATUS "Termin: Core SDK profile enabled")
else()
    add_subdirectory(graphics)

    if(TERMIN_SDK_PROFILE STREQUAL "graphics")
        # Core + Graphics is the complete target graph for this SDK profile.
    elseif(TERMIN_PLATFORM_WEB)
        add_subdirectory(engine/termin-modules)
        add_subdirectory(engine/termin-scene)
        add_subdirectory(engine/termin-input)
        add_subdirectory(physics/termin-collision)
        add_subdirectory(engine/termin-components/termin-components-mesh)
        add_subdirectory(engine/termin-lighting)
        add_subdirectory(engine/termin-render)
        add_subdirectory(engine/termin-components/termin-components-skeleton)
        add_subdirectory(engine/termin-display)
        add_subdirectory(engine/termin-components/termin-components-render)
        add_subdirectory(engine/termin-render-passes)
        add_subdirectory(engine/termin-engine)
        add_subdirectory(engine/termin-bootstrap)
        add_subdirectory(engine/termin-runtime)
        add_subdirectory(platform/termin-web-core)
    else()
        add_subdirectory(engine/termin-profiler-remote)
        add_subdirectory(engine/termin-framegraph-remote)
        add_subdirectory(engine/termin-audio)
        add_subdirectory(engine/termin-modules)
        add_subdirectory(engine/termin-csg)
        add_subdirectory(engine/termin-voxels)
        add_subdirectory(engine/termin-scene)
        add_subdirectory(engine/termin-prefab)
        add_subdirectory(engine/termin-lighting)
        add_subdirectory(engine/termin-input)
        add_subdirectory(physics/termin-collision)
        add_subdirectory(physics/termin-qopt)
        add_subdirectory(physics/termin-robotics)
        add_subdirectory(physics/termin-physics-qopt)
        add_subdirectory(physics/termin-physics)
        add_subdirectory(engine/termin-components/termin-components-mesh)
        add_subdirectory(engine/termin-components/termin-components-kinematic)

        add_subdirectory(engine/termin-render)
        add_subdirectory(engine/termin-components/termin-components-collision)
        add_subdirectory(engine/termin-components/termin-components-physics)
        add_subdirectory(engine/termin-components/termin-components-physics-fem)
        add_subdirectory(engine/termin-components/termin-components-skeleton)
        add_subdirectory(engine/termin-display)
        add_subdirectory(engine/termin-components/termin-components-ui)
        add_subdirectory(engine/termin-components/termin-components-physics-fem-ui)
        add_subdirectory(engine/termin-components/termin-components-render)
        add_subdirectory(physics/termin-navmesh)
        add_subdirectory(engine/termin-components/termin-components-foliage)
        add_subdirectory(engine/termin-render-passes)
        add_subdirectory(engine/termin-engine)
        add_subdirectory(engine/termin-frame-profiler)
        add_subdirectory(engine/termin-framegraph-remote-target)
        add_subdirectory(engine/termin-framegraph-remote-client)

        if(NOT TERMIN_PLATFORM_ANDROID)
            add_subdirectory(engine/termin-profiler)
            add_subdirectory(engine/termin-components/termin-components-animation)
        endif()

        add_subdirectory(engine/termin-bootstrap)
        add_subdirectory(engine/termin-runtime)

        if(TERMIN_PLATFORM_ANDROID)
            add_subdirectory(platform/termin-openxr)
            add_subdirectory(platform/termin-android)
        endif()

        if(NOT TERMIN_PLATFORM_ANDROID)
            add_subdirectory(editor/termin-player)
            add_subdirectory(editor/termin-cli)
            add_subdirectory(editor/termin-app/cpp)
        endif()
    endif()
endif()
if(TERMIN_BUILD_TESTS)
    foreach(_termin_aggregate IN ITEMS
            TERMIN_NATIVE_TEST_TARGETS
            TERMIN_NATIVE_TEST_TARGETS_WITH_WINDOW)
        get_property(
            ${_termin_aggregate}
            GLOBAL
            PROPERTY ${_termin_aggregate}
        )
        list(REMOVE_DUPLICATES ${_termin_aggregate})
        list(LENGTH ${_termin_aggregate} _termin_aggregate_target_count)
        if(_termin_aggregate_target_count EQUAL 0)
            message(FATAL_ERROR
                "TERMIN_BUILD_TESTS=ON produced no targets for "
                "${_termin_aggregate}")
        endif()
    endforeach()
    add_custom_target(termin_native_tests)
    add_dependencies(
        termin_native_tests
        ${TERMIN_NATIVE_TEST_TARGETS}
    )
    add_custom_target(termin_native_tests_with_window)
    add_dependencies(
        termin_native_tests_with_window
        ${TERMIN_NATIVE_TEST_TARGETS_WITH_WINDOW}
    )

    # The repository test planner validates its exact executable selection
    # against this manifest before asking the native build tool for one of the
    # aggregate targets.  Keeping the aggregate membership in CMake avoids
    # hundreds of independent Make goal traversals without weakening planner
    # capability filtering.
    set(_termin_test_aggregate_manifest "schema=1\n")
    foreach(_termin_target IN LISTS TERMIN_NATIVE_TEST_TARGETS)
        string(APPEND _termin_test_aggregate_manifest
            "termin_native_tests\t${_termin_target}\n")
    endforeach()
    foreach(_termin_target IN LISTS TERMIN_NATIVE_TEST_TARGETS_WITH_WINDOW)
        string(APPEND _termin_test_aggregate_manifest
            "termin_native_tests_with_window\t${_termin_target}\n")
    endforeach()
    file(WRITE
        "${CMAKE_CURRENT_BINARY_DIR}/ctest-build-aggregates.txt"
        "${_termin_test_aggregate_manifest}"
    )

    # Shader-driven native tests must use the compiler from this exact build
    # graph.  It is a support tool rather than a CTest executable, so it is an
    # explicit dependency but intentionally absent from the membership file.
    if(NOT TARGET termin_shaderc)
        message(FATAL_ERROR
            "TERMIN_BUILD_TESTS=ON produced no termin_shaderc target")
    endif()
    add_dependencies(termin_native_tests termin_shaderc)
    add_dependencies(termin_native_tests_with_window termin_shaderc)
endif()
