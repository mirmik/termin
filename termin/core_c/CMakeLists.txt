# core_c - Pure C library for Termin engine core
# No C++ or Python dependencies
cmake_minimum_required(VERSION 3.14)
project(termin_core C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Options
option(TC_BUILD_SHARED "Build shared library" ON)
option(TC_BUILD_TESTS "Build tests" ON)
option(TC_USE_EXTERNAL_INSPECT "Use external termin_inspect package for inspect/kind core" ON)

# Source files (only .c)
# Note: tc_collision.c is NOT included here because collision detection
# requires C++ CollisionWorld from termin.dll. The C API is implemented
# in cpp/termin/tc_collision_c_api.cpp instead.
set(TC_SOURCES
    src/tc_animation_registry.c
    src/tc_core.c
    src/tc_primitive_mesh.c
    src/tc_picking.c
    src/tc_skeleton_registry.c
)

if(NOT TC_USE_EXTERNAL_INSPECT)
    message(FATAL_ERROR "TC_USE_EXTERNAL_INSPECT=OFF is no longer supported: inspect/kind core sources were moved to termin_inspect")
endif()

find_package(termin_inspect REQUIRED)
set(TC_EXTERNAL_INSPECT_ACTIVE ON CACHE INTERNAL "termin_core uses external termin_inspect")
message(STATUS "termin_core: using external termin_inspect package")

# Header files (only .h, for IDE integration)
set(TC_HEADERS
    include/geom/tc_pose.h
    include/geom/tc_vec3.h
    include/geom/tc_quat.h
    include/inspect/tc_inspect_init.h
    include/inspect/tc_inspect_context.h
    include/inspect/tc_inspect_component_adapter.h
    include/resources/tc_animation.h
    include/resources/tc_animation_registry.h
    include/physics/tc_collision.h
    include/tc_picking.h
    include/resources/tc_skeleton.h
    include/resources/tc_skeleton_registry.h
    include/core/tc_scene_registry.h
    include/tc_types.h
    include/termin_core.h
)

find_package(termin_scene REQUIRED)
find_package(termin_input REQUIRED)
find_package(termin_render REQUIRED)
find_package(termin_display REQUIRED)

# termin-base (provides tc_log, shared enums)
find_package(termin_base REQUIRED)

# termin-graphics (provides tgfx types, gpu_ops, opengl backend)
find_package(termin_graphics REQUIRED)

# Library target
if(TC_BUILD_SHARED)
    add_library(termin_core SHARED ${TC_SOURCES} ${TC_HEADERS})
    target_compile_definitions(termin_core PRIVATE TC_EXPORTS)
else()
    add_library(termin_core STATIC ${TC_SOURCES} ${TC_HEADERS})
endif()

set_target_properties(termin_core PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    INSTALL_RPATH "$ORIGIN"
)

target_include_directories(termin_core
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_link_libraries(termin_core PUBLIC tgfx::termin_graphics tcbase::termin_base)
target_link_libraries(termin_core PUBLIC termin_scene::termin_scene)
target_link_libraries(termin_core PUBLIC termin_input::termin_input)
target_link_libraries(termin_core PUBLIC termin_inspect::termin_inspect)
target_link_libraries(termin_core PUBLIC termin_render::termin_render)
target_link_libraries(termin_core PUBLIC termin_display::termin_display)

# Platform-specific
if(WIN32)
    target_link_libraries(termin_core PRIVATE winmm)
    target_compile_definitions(termin_core PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()

if(UNIX AND NOT APPLE)
    target_link_libraries(termin_core PRIVATE m)
endif()

# Compiler warnings
if(MSVC)
    target_compile_options(termin_core PRIVATE /W3)
else()
    target_compile_options(termin_core PRIVATE -Wall -Wextra -Wno-stringop-truncation)
endif()

# Tests
if(TC_BUILD_TESTS)
    enable_testing()

    if(NOT TARGET termin_render::termin_render)
        find_package(termin_render REQUIRED)
    endif()

    add_executable(termin_core_test tests/test_main.c)
    target_link_libraries(termin_core_test PRIVATE termin_core termin_render::termin_render)
    if(UNIX AND NOT APPLE)
        target_link_libraries(termin_core_test PRIVATE m)
    endif()
    add_test(NAME termin_core_test COMMAND termin_core_test)

    # Put test executables next to the DLL so they can find it
    set_target_properties(
        termin_core_test
        PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
endif()

# Install
install(TARGETS termin_core
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(FILES ${TC_HEADERS} DESTINATION include/termin_core)
