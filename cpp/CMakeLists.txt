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
find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 CONFIG REQUIRED)

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR})

# Geom native module (Vec3, Quat, Pose3, Screw3, GeneralPose3, Transform, AABB)
pybind11_add_module(_geom_native
    termin/bindings/geom/geom_module.cpp
    termin/bindings/geom/vec3.cpp
    termin/bindings/geom/quat.cpp
    termin/bindings/geom/mat44.cpp
    termin/bindings/geom/pose3.cpp
    termin/bindings/geom/general_pose3.cpp
    termin/bindings/geom/screw3.cpp
    termin/bindings/geom/transform.cpp
    termin/bindings/geom/aabb.cpp
)
target_compile_options(_geom_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)
target_link_libraries(_geom_native PRIVATE entity_lib)

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

# Lighting native module (Light, AttenuationCoefficients)
pybind11_add_module(_lighting_native termin/lighting_bindings.cpp)
target_compile_options(_lighting_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Trent library (shared by all resource modules)
# trent library - STATIC on Windows (avoids DLL import library issues), SHARED on Linux
if(WIN32)
    add_library(trent STATIC
        trent/trent.cpp
        trent/trent_path.cpp
        trent/string_ext.cpp
    )
else()
    add_library(trent SHARED
        trent/trent.cpp
        trent/trent_path.cpp
        trent/string_ext.cpp
    )
endif()
target_compile_options(trent PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)
set_target_properties(trent PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    # Explicit output directories for multi-config builds
    ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
    ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${CMAKE_BINARY_DIR}/bin
    ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_BINARY_DIR}/bin
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
    LIBRARY_OUTPUT_DIRECTORY_DEBUG ${CMAKE_BINARY_DIR}/bin
    LIBRARY_OUTPUT_DIRECTORY_RELEASE ${CMAKE_BINARY_DIR}/bin
)

# Mesh native module (Mesh3, SkinnedMesh3, MeshHandle) - separate module
pybind11_add_module(_mesh_native
    termin/bindings/mesh/mesh_module.cpp
    termin/mesh_bindings.cpp
)
target_link_libraries(_mesh_native PRIVATE trent entity_lib)
target_compile_options(_mesh_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Skeleton native module (Bone, SkeletonData, SkeletonHandle) - separate module
pybind11_add_module(_skeleton_native
    termin/bindings/skeleton/skeleton_module.cpp
)
target_link_libraries(_skeleton_native PRIVATE trent entity_lib)
target_compile_options(_skeleton_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Texture native module (TextureData) - separate module
pybind11_add_module(_texture_native
    termin/bindings/texture/texture_module.cpp
)
target_compile_options(_texture_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Find OpenGL (needed by _graphics_native and _native)
find_package(OpenGL REQUIRED)

# Graphics native module (GraphicsBackend, OpenGLGraphicsBackend, GPU handles)
pybind11_add_module(_graphics_native
    termin/bindings/graphics/graphics_module.cpp
    termin/render/glad/src/glad.c
)
target_include_directories(_graphics_native PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/termin/render/glad/include
)
target_link_libraries(_graphics_native PRIVATE OpenGL::GL)
target_compile_options(_graphics_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Entity shared library (shared by _entity_native and _native)
# Must be SHARED so that singletons (ComponentRegistry, InspectRegistry, EntityRegistry)
# are the same instance across all Python extension modules.
add_library(entity_lib SHARED
    termin/entity/entity.cpp
    termin/entity/entity_registry.cpp
    termin/entity/entity_handle.cpp
    termin/entity/component_registry.cpp
    termin/entity/vtable_utils.cpp
    termin/entity/components/rotator_component.cpp
    termin/inspect/inspect_registry.cpp
)
target_link_libraries(entity_lib PRIVATE trent pybind11::headers Python3::Python)
target_compile_definitions(entity_lib PRIVATE ENTITY_LIB_EXPORTS)
target_compile_options(entity_lib PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)
set_target_properties(entity_lib PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

# Entity native module (Component, Entity, EntityHandle, registries)
pybind11_add_module(_entity_native
    termin/bindings/entity/entity_module.cpp
)
target_link_libraries(_entity_native PRIVATE entity_lib trent)
target_compile_options(_entity_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Animation native module (Channel, Clip, AnimationClipHandle)
# Must be after entity_lib since it links against it
pybind11_add_module(_animation_native termin/bindings/animation/animation_module.cpp)
target_link_libraries(_animation_native PRIVATE trent entity_lib)
target_compile_options(_animation_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)
set_target_properties(_animation_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)

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

# Unified native module (Render + SDL + Scene + Skeleton + Inspect + Assets)
# Note: Mesh3/SkinnedMesh3 are in separate _mesh_native module, imported at runtime
# Note: Graphics types (Color4, Size2i, etc), GraphicsBackend, handles are in _graphics_native
# Note: Component, Entity, EntityHandle are in _entity_native module, imported at runtime
pybind11_add_module(_native
    termin/bindings.cpp
    termin/bindings/render/render_module.cpp
    termin/bindings/render/shader.cpp
    termin/bindings/render/shader_parser.cpp
    termin/bindings/render/camera.cpp
    termin/bindings/render/shadow.cpp
    termin/bindings/render/resource_spec.cpp
    termin/bindings/render/immediate.cpp
    termin/bindings/render/frame_pass.cpp
    termin/bindings/render/material.cpp
    termin/bindings/render/drawable.cpp
    termin/bindings/render/gpu.cpp
    termin/bindings/render/renderers.cpp
    termin/sdl_bindings.cpp
    termin/scene_bindings.cpp
    termin/skeleton_bindings.cpp
    termin/inspect_bindings.cpp
    termin/assets/assets_bindings.cpp
    termin/assets/handles.cpp
    termin/render/shader_parser.cpp
    termin/render/shadow_camera.cpp
    termin/render/immediate_renderer.cpp
    termin/render/material.cpp
    termin/render/mesh_gpu.cpp
    termin/render/texture_gpu.cpp
    termin/render/skinned_mesh_renderer.cpp
    termin/render/skeleton_controller.cpp
    termin/render/mesh_renderer.cpp
    termin/scene/scene.cpp
    termin/skeleton/skeleton_instance.cpp
    termin/render/glad/src/glad.c
)
target_include_directories(_native PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/termin/render/glad/include
    ${SDL2_INCLUDE_DIRS}
)
target_link_libraries(_native PRIVATE OpenGL::GL ${SDL2_LIBRARIES} trent entity_lib)

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
# Install libtrent to root termin directory
install(TARGETS trent DESTINATION ${CMAKE_INSTALL_PREFIX})

# Set RPATH for modules that depend on libtrent
set_target_properties(_mesh_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_skeleton_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_entity_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_native PROPERTIES
    INSTALL_RPATH "$ORIGIN"
    BUILD_WITH_INSTALL_RPATH TRUE
)

install(TARGETS _geom_native DESTINATION ${CMAKE_INSTALL_PREFIX}/geombase)
install(TARGETS _colliders_native DESTINATION ${CMAKE_INSTALL_PREFIX}/colliders)
install(TARGETS _physics_native DESTINATION ${CMAKE_INSTALL_PREFIX}/physics)
install(TARGETS _voxels_native DESTINATION ${CMAKE_INSTALL_PREFIX}/voxels)
install(TARGETS _collision_native DESTINATION ${CMAKE_INSTALL_PREFIX}/collision)
install(TARGETS _animation_native DESTINATION ${CMAKE_INSTALL_PREFIX}/visualization/animation)
install(TARGETS _lighting_native DESTINATION ${CMAKE_INSTALL_PREFIX}/lighting)
install(TARGETS _mesh_native DESTINATION ${CMAKE_INSTALL_PREFIX}/mesh)
install(TARGETS _skeleton_native DESTINATION ${CMAKE_INSTALL_PREFIX}/skeleton)
install(TARGETS _texture_native DESTINATION ${CMAKE_INSTALL_PREFIX}/texture)
install(TARGETS _graphics_native DESTINATION ${CMAKE_INSTALL_PREFIX}/graphics)
install(TARGETS _entity_native DESTINATION ${CMAKE_INSTALL_PREFIX}/entity)
install(TARGETS _native DESTINATION ${CMAKE_INSTALL_PREFIX})
