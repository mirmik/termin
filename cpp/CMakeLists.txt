cmake_minimum_required(VERSION 3.14)
project(termin_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Optimization flags
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -march=native -DNDEBUG")

# Find pybind11 via pip
execute_process(
    COMMAND python3 -m pybind11 --cmakedir
    OUTPUT_VARIABLE pybind11_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
find_package(pybind11 CONFIG REQUIRED)

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)

# Geom native module (Vec3, Quat, Pose3, Screw3)
pybind11_add_module(_geom_native src/bindings.cpp)
target_compile_options(_geom_native PRIVATE
    $<$<CONFIG:Release>:-O3 -march=native -ffast-math>
)

# Colliders native module (BoxCollider, SphereCollider)
pybind11_add_module(_colliders_native src/colliders_bindings.cpp)
target_compile_options(_colliders_native PRIVATE
    $<$<CONFIG:Release>:-O3 -march=native -ffast-math>
)

# Physics native module (RigidBody, PhysicsWorld, Contact)
pybind11_add_module(_physics_native src/physics_bindings.cpp)
target_compile_options(_physics_native PRIVATE
    $<$<CONFIG:Release>:-O3 -march=native -ffast-math>
)

# Install to python packages
install(TARGETS _geom_native DESTINATION ${CMAKE_INSTALL_PREFIX}/geombase)
install(TARGETS _colliders_native DESTINATION ${CMAKE_INSTALL_PREFIX}/colliders)
install(TARGETS _physics_native DESTINATION ${CMAKE_INSTALL_PREFIX}/physics)
