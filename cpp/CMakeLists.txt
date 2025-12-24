cmake_minimum_required(VERSION 3.14)
project(termin_native LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Default CTest config for multi-config generators so plain `ctest .` works
if(CMAKE_CONFIGURATION_TYPES)
    if(NOT CTEST_CONFIGURATION_TYPE)
        set(CTEST_CONFIGURATION_TYPE "Debug" CACHE STRING "Default CTest config" FORCE)
    endif()
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
    set(CMAKE_CXX_FLAGS_RELEASE "/O2 /DNDEBUG")
    set(OPTIMIZE_FLAGS /O2 /fp:fast)
else()
    set(CMAKE_CXX_FLAGS_RELEASE "-O3 -march=native -DNDEBUG")
    set(OPTIMIZE_FLAGS -O3 -march=native -ffast-math)
endif()

# Find pybind11 via pip (works on both Windows and Linux)
if(WIN32)
    execute_process(
        COMMAND python -m pybind11 --cmakedir
        OUTPUT_VARIABLE pybind11_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
else()
    execute_process(
        COMMAND python3 -m pybind11 --cmakedir
        OUTPUT_VARIABLE pybind11_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
endif()
find_package(pybind11 CONFIG REQUIRED)

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR})

# Geom native module (Vec3, Quat, Pose3, Screw3, GeneralPose3)
pybind11_add_module(_geom_native termin/geom_bindings.cpp)
target_compile_options(_geom_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Colliders native module (BoxCollider, SphereCollider)
pybind11_add_module(_colliders_native termin/colliders_bindings.cpp)
target_compile_options(_colliders_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Physics native module (RigidBody, PhysicsWorld, Contact)
pybind11_add_module(_physics_native termin/physics_bindings.cpp)
target_compile_options(_physics_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Voxels native module (VoxelGrid, voxelization)
pybind11_add_module(_voxels_native termin/voxels_bindings.cpp)
target_compile_options(_voxels_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Collision native module (BVH, CollisionWorld, ContactManifold)
pybind11_add_module(_collision_native termin/collision_bindings.cpp)
target_compile_options(_collision_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Animation native module (Channel, Clip)
pybind11_add_module(_animation_native termin/animation_bindings.cpp)
target_compile_options(_animation_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Lighting native module (Light, AttenuationCoefficients)
pybind11_add_module(_lighting_native termin/lighting_bindings.cpp)
target_compile_options(_lighting_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)


# Find OpenGL (needed by _native)
find_package(OpenGL REQUIRED)

# Find SDL2 (required)
if(WIN32)
    # Check common Windows locations
    set(SDL2_SEARCH_PATHS
        "C:/SDL2"
        "$ENV{SDL2_DIR}"
        "$ENV{PROGRAMFILES}/SDL2"
    )
    # Find SDL2 include directory (parent of SDL2/SDL.h)
    find_path(SDL2_INCLUDE_DIRS SDL2/SDL.h
        PATH_SUFFIXES include
        PATHS ${SDL2_SEARCH_PATHS}
    )
    find_library(SDL2_LIBRARIES
        NAMES SDL2
        PATH_SUFFIXES lib/x64 lib
        PATHS ${SDL2_SEARCH_PATHS}
    )
    find_library(SDL2MAIN_LIBRARY
        NAMES SDL2main
        PATH_SUFFIXES lib/x64 lib
        PATHS ${SDL2_SEARCH_PATHS}
    )
    if(SDL2_INCLUDE_DIRS AND SDL2_LIBRARIES)
        set(SDL2_FOUND TRUE)
        if(SDL2MAIN_LIBRARY)
            list(APPEND SDL2_LIBRARIES ${SDL2MAIN_LIBRARY})
        endif()
        message(STATUS "Found SDL2: ${SDL2_INCLUDE_DIRS}")
    else()
        message(FATAL_ERROR "SDL2 not found. Set SDL2_DIR or install to C:\\SDL2")
    endif()
else()
    find_package(SDL2 QUIET)
    if(NOT SDL2_FOUND)
        find_package(PkgConfig REQUIRED)
        pkg_check_modules(SDL2 REQUIRED sdl2)
    endif()
endif()

# Unified native module (Mesh3 + Render + SDL + Entity + Scene + Skeleton + Inspect + Assets)
pybind11_add_module(_native
    termin/bindings.cpp
    termin/mesh_bindings.cpp
    termin/render_bindings.cpp
    termin/sdl_bindings.cpp
    termin/entity_bindings.cpp
    termin/scene_bindings.cpp
    termin/skeleton_bindings.cpp
    termin/inspect_bindings.cpp
    termin/assets/assets_bindings.cpp
    termin/render/shader_parser.cpp
    termin/render/shadow_camera.cpp
    termin/render/immediate_renderer.cpp
    termin/entity/entity.cpp
    termin/entity/entity_registry.cpp
    termin/entity/component_registry.cpp
    termin/entity/vtable_utils.cpp
    termin/entity/components/rotator_component.cpp
    termin/scene/scene.cpp
    termin/skeleton/skeleton_instance.cpp
    termin/render/glad/src/glad.c
    trent/trent.cpp
    trent/trent_path.cpp
    trent/string_ext.cpp
)
target_include_directories(_native PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/termin/render/glad/include
    ${SDL2_INCLUDE_DIRS}
)
target_link_libraries(_native PRIVATE OpenGL::GL ${SDL2_LIBRARIES})

if(UNIX AND NOT APPLE)
    target_link_libraries(_native PRIVATE ${CMAKE_DL_LIBS})
endif()
target_compile_options(_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# ---------------- Tests ----------------
enable_testing()

# Default config for multi-config generators so that plain `ctest` works
set(DEFAULT_CTEST_CONFIG "Debug")
configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/CTestCustom.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/CTestCustom.cmake
    @ONLY
)

add_executable(termin_tests
    tests/main.cpp
    tests/tests_general_pose3.cpp
    tests/tests_general_transform3.cpp
    tests/tests_colliders.cpp
    tests/tests_collision.cpp
)
target_include_directories(termin_tests PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/tests
)
target_compile_options(termin_tests PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)
add_test(NAME termin_tests COMMAND ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin_tests${CMAKE_EXECUTABLE_SUFFIX})

# Pybind module to run C++ tests from Python
pybind11_add_module(_cpp_tests
    tests/tests_binding.cpp
    tests/tests_general_pose3.cpp
    tests/tests_general_transform3.cpp
    tests/tests_colliders.cpp
    tests/tests_collision.cpp
)
target_include_directories(_cpp_tests PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/tests
)
target_compile_options(_cpp_tests PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)
install(TARGETS _cpp_tests DESTINATION ${CMAKE_INSTALL_PREFIX}/tests)

# Convenience target to run tests with correct config on multi-config generators (MSVC)
add_custom_target(run_tests
    COMMAND ${CMAKE_CTEST_COMMAND} --output-on-failure -C $<CONFIG>
    DEPENDS termin_tests
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
    COMMENT "Running C++ tests")

# Install to python packages
install(TARGETS _geom_native DESTINATION ${CMAKE_INSTALL_PREFIX}/geombase)
install(TARGETS _colliders_native DESTINATION ${CMAKE_INSTALL_PREFIX}/colliders)
install(TARGETS _physics_native DESTINATION ${CMAKE_INSTALL_PREFIX}/physics)
install(TARGETS _voxels_native DESTINATION ${CMAKE_INSTALL_PREFIX}/voxels)
install(TARGETS _collision_native DESTINATION ${CMAKE_INSTALL_PREFIX}/collision)
install(TARGETS _animation_native DESTINATION ${CMAKE_INSTALL_PREFIX}/visualization/animation)
install(TARGETS _lighting_native DESTINATION ${CMAKE_INSTALL_PREFIX}/lighting)
install(TARGETS _native DESTINATION ${CMAKE_INSTALL_PREFIX})
