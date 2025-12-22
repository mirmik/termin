cmake_minimum_required(VERSION 3.14)
project(termin_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
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

# Entity native module (Entity, Component, registries)
pybind11_add_module(_entity_native
    termin/entity_bindings.cpp
    termin/entity/entity.cpp
    termin/entity/entity_registry.cpp
    termin/entity/component_registry.cpp
    termin/entity/components/rotator_component.cpp
)
target_compile_options(_entity_native PRIVATE
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
install(TARGETS _entity_native DESTINATION ${CMAKE_INSTALL_PREFIX}/entity)
