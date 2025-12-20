cmake_minimum_required(VERSION 3.14)
project(termin_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

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

# ---------------- Tests ----------------
enable_testing()
add_executable(termin_tests
    tests/main.cpp
    tests/tests_general_pose3.cpp
)
target_include_directories(termin_tests PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/tests
)
target_compile_options(termin_tests PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)
add_test(NAME termin_tests COMMAND termin_tests)

# Install to python packages
install(TARGETS _geom_native DESTINATION ${CMAKE_INSTALL_PREFIX}/geombase)
install(TARGETS _colliders_native DESTINATION ${CMAKE_INSTALL_PREFIX}/colliders)
install(TARGETS _physics_native DESTINATION ${CMAKE_INSTALL_PREFIX}/physics)
install(TARGETS _voxels_native DESTINATION ${CMAKE_INSTALL_PREFIX}/voxels)
