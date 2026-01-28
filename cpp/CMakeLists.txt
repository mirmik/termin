cmake_minimum_required(VERSION 3.16)
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

find_package(Python COMPONENTS Interpreter Development REQUIRED)

# Find nanobind via pip
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

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR})

# Geom native module (Vec3, Quat, Pose3, Screw3, GeneralPose3, Transform, AABB) - using nanobind
nanobind_add_module(_geom_native
    termin/bindings/geom/geom_module.cpp
    termin/bindings/geom/vec3.cpp
    termin/bindings/geom/vec4.cpp
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

# Colliders native module (BoxCollider, SphereCollider) - using nanobind
nanobind_add_module(_colliders_native termin/colliders_bindings.cpp)
target_link_libraries(_colliders_native PRIVATE entity_lib)
target_compile_options(_colliders_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Physics native module (RigidBody, PhysicsWorld, Contact) - using nanobind
nanobind_add_module(_physics_native termin/physics_bindings.cpp)
target_link_libraries(_physics_native PRIVATE entity_lib)
target_compile_options(_physics_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Voxels native module (VoxelGrid, voxelization, VoxelGridHandle) - using nanobind
nanobind_add_module(_voxels_native termin/voxels_bindings.cpp)
target_compile_options(_voxels_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)
target_link_libraries(_voxels_native PRIVATE entity_lib trent)

# Collision native module (BVH, CollisionWorld, ContactManifold) - using nanobind
nanobind_add_module(_collision_native termin/collision_bindings.cpp)
target_link_libraries(_collision_native PRIVATE entity_lib)
target_compile_options(_collision_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Lighting native module (Light, AttenuationCoefficients) - using nanobind
nanobind_add_module(_lighting_native termin/lighting_bindings.cpp)
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
        trent/yaml.cpp
    )
else()
    add_library(trent SHARED
        trent/trent.cpp
        trent/trent_path.cpp
        trent/string_ext.cpp
        trent/yaml.cpp
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

# Mesh native module (Mesh3, TcMesh, MeshHandle) - using nanobind
nanobind_add_module(_mesh_native
    termin/bindings/mesh/mesh_module.cpp
    termin/mesh_bindings.cpp
    termin/mesh/tc_mesh.cpp
)
target_link_libraries(_mesh_native PRIVATE trent entity_lib)
target_compile_options(_mesh_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Skeleton native module (Bone, SkeletonData, SkeletonInstance, SkeletonController) - using nanobind
# Implementation is in entity_lib, this module only contains bindings
nanobind_add_module(_skeleton_native
    termin/bindings/skeleton/skeleton_module.cpp
)
target_link_libraries(_skeleton_native PRIVATE trent entity_lib skeleton_lib)
target_compile_options(_skeleton_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Texture native module (TcTexture, TcTexture) - using nanobind
nanobind_add_module(_texture_native
    termin/bindings/texture/texture_module.cpp
    termin/texture/tc_texture_handle.cpp
)
target_link_libraries(_texture_native PRIVATE trent entity_lib)
target_compile_options(_texture_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Find OpenGL (needed by _graphics_native and _native)
find_package(OpenGL REQUIRED)

# Disable optimizations for glad.c (large file, slow to compile with -O2)
set_source_files_properties(
    termin/render/glad/src/glad.c
    PROPERTIES COMPILE_OPTIONS "-O0"
)

# Graphics native module (GraphicsBackend, OpenGLGraphicsBackend, GPU handles) - nanobind
nanobind_add_module(_graphics_native
    termin/bindings/graphics/graphics_module.cpp
    termin/render/glad/src/glad.c
)
target_include_directories(_graphics_native PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/termin/render/glad/include
)
target_link_libraries(_graphics_native PRIVATE OpenGL::GL entity_lib)
target_compile_options(_graphics_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Core C library
set(TC_BUILD_TESTS OFF CACHE BOOL "" FORCE)
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../core_c ${CMAKE_CURRENT_BINARY_DIR}/core_c)

# Recastnavigation (static libraries for navmesh building)
set(RECASTNAVIGATION_DEMO OFF CACHE BOOL "" FORCE)
set(RECASTNAVIGATION_TESTS OFF CACHE BOOL "" FORCE)
set(RECASTNAVIGATION_EXAMPLES OFF CACHE BOOL "" FORCE)
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../third/recastnavigation ${CMAKE_CURRENT_BINARY_DIR}/recastnavigation)

# Entity shared library (shared by _entity_native and _native)
# Must be SHARED so that singletons (ComponentRegistry, InspectRegistry, EntityRegistry)
# are the same instance across all Python extension modules.
set(ENTITY_LIB_SOURCES
    termin/entity/entity.cpp
    termin/entity/entity_registry.cpp
    termin/entity/component.cpp
    termin/entity/component_registry.cpp
    termin/entity/vtable_utils.cpp
    termin/entity/input_handler.cpp
    termin/entity/components/rotator_component.cpp
    termin/camera/camera_component.cpp
    termin/camera/orbit_camera_controller.cpp
    termin/geom/general_transform3.cpp
    ../core_c/src/tc_inspect_instance.cpp
    termin/inspect/tc_kind_cpp.cpp
    termin/modules/module_loader.cpp
)
# Python-specific sources (require nanobind)
if(NOT BUILD_CSHARP_BINDINGS)
    list(APPEND ENTITY_LIB_SOURCES
        termin/bindings/inspect/tc_kind_python_instance.cpp
    )
endif()
add_library(entity_lib SHARED ${ENTITY_LIB_SOURCES})
target_include_directories(entity_lib PUBLIC ../core_c/include ${CMAKE_CURRENT_SOURCE_DIR})
if(BUILD_CSHARP_BINDINGS)
    target_link_libraries(entity_lib PUBLIC termin_core PRIVATE trent)
else()
    target_link_libraries(entity_lib PUBLIC termin_core PRIVATE trent nanobind-static Python::Python)
    target_compile_definitions(entity_lib PRIVATE TERMIN_HAS_NANOBIND)
endif()
target_compile_definitions(entity_lib PRIVATE ENTITY_LIB_EXPORTS TC_EXPORTS)
target_compile_options(entity_lib PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)
target_precompile_headers(entity_lib PRIVATE termin/pch.hpp)
set_target_properties(entity_lib PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

# Render library (Drawable vtable, shared by components that need rendering)
# Includes passes with TC_REGISTER_FRAME_PASS for static registration
add_library(render_lib STATIC
    termin/render/drawable.cpp
    termin/render/mesh_renderer.cpp
    termin/render/frame_pass.cpp
    termin/render/fbo_pool.cpp
    termin/render/render_engine.cpp
    termin/render/render_pipeline.cpp
    termin/render/rendering_manager.cpp
    termin/render/color_pass.cpp
    termin/render/depth_pass.cpp
    termin/render/normal_pass.cpp
    termin/render/shadow_pass.cpp
    termin/render/id_pass.cpp
    termin/render/shader_parser.cpp
    termin/render/shadow_camera.cpp
    termin/render/glsl_preprocessor.cpp
    termin/lighting/shadow.cpp
    termin/texture/tc_texture_handle.cpp
)
target_include_directories(render_lib PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/termin/render/glad/include
)
target_link_libraries(render_lib PUBLIC entity_lib trent OpenGL::GL)
if(NOT BUILD_CSHARP_BINDINGS)
    target_include_directories(render_lib PRIVATE
        $<TARGET_PROPERTY:nanobind-static,INTERFACE_INCLUDE_DIRECTORIES>
        ${Python_INCLUDE_DIRS}
    )
    target_compile_definitions(render_lib PRIVATE TERMIN_HAS_NANOBIND)
endif()
target_compile_options(render_lib PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)
set_target_properties(render_lib PROPERTIES
    POSITION_INDEPENDENT_CODE ON
)

# NavMesh library (RecastNavMeshBuilderComponent)
add_library(navmesh_lib STATIC
    termin/navmesh/recast_navmesh_builder_component.cpp
)
target_include_directories(navmesh_lib PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/../third/recastnavigation/Recast/Include
)
target_link_libraries(navmesh_lib PUBLIC entity_lib render_lib Recast)
target_include_directories(navmesh_lib PRIVATE
    $<TARGET_PROPERTY:nanobind-static,INTERFACE_INCLUDE_DIRECTORIES>
    ${Python_INCLUDE_DIRS}
)
target_compile_options(navmesh_lib PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)
set_target_properties(navmesh_lib PROPERTIES
    POSITION_INDEPENDENT_CODE ON
)

# Skeleton static library (linked into _skeleton_native, _animation_native, _native)
# Static because it uses nanobind runtime and can't be a DLL without symbol conflicts
add_library(skeleton_lib STATIC
    termin/skeleton/skeleton_instance.cpp
    termin/render/skeleton_controller.cpp
)
target_link_libraries(skeleton_lib PUBLIC entity_lib PRIVATE trent)
# Need nanobind and Python includes for compilation
target_include_directories(skeleton_lib PRIVATE
    $<TARGET_PROPERTY:nanobind-static,INTERFACE_INCLUDE_DIRECTORIES>
    ${Python_INCLUDE_DIRS}
)
target_compile_options(skeleton_lib PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)
set_target_properties(skeleton_lib PROPERTIES
    POSITION_INDEPENDENT_CODE ON
)

# Viewport native module (TcViewport) - nanobind
# Must be before _entity_native since CameraComponent uses TcViewport
nanobind_add_module(_viewport_native
    termin/bindings/viewport/viewport_module.cpp
)
target_link_libraries(_viewport_native PRIVATE entity_lib)
target_compile_definitions(_viewport_native PRIVATE TERMIN_HAS_NANOBIND)
target_compile_options(_viewport_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Entity native module (Component, Entity, registries) - nanobind
nanobind_add_module(_entity_native
    termin/bindings/entity/entity_module.cpp
    termin/bindings/entity/entity_bindings.cpp
    termin/bindings/camera/camera_bindings.cpp
    termin/bindings/camera/orbit_camera_bindings.cpp
    termin/bindings/input/input_events_bindings.cpp
)
target_link_libraries(_entity_native PRIVATE entity_lib trent)
target_compile_definitions(_entity_native PRIVATE TERMIN_HAS_NANOBIND)
target_compile_options(_entity_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# Animation native module (TcAnimationClip, AnimationPlayer) - nanobind
# Must be after entity_lib since it links against it
nanobind_add_module(_animation_native
    termin/bindings/animation/animation_module.cpp
    termin/animation/animation_player.cpp
)
target_link_libraries(_animation_native PRIVATE trent entity_lib skeleton_lib)
target_compile_options(_animation_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)

# NavMesh native module (RecastNavMeshBuilderComponent) - nanobind
nanobind_add_module(_navmesh_native
    termin/bindings/navmesh/navmesh_module.cpp
)
target_link_libraries(_navmesh_native PRIVATE trent entity_lib navmesh_lib render_lib)
target_compile_options(_navmesh_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
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

# Unified native module (Render + SDL + Scene + Skeleton + Inspect + Assets) - nanobind
# Note: Mesh3/SkinnedMesh3 are in separate _mesh_native module, imported at runtime
# Note: Graphics types (Color4, Size2i, etc), GraphicsBackend, handles are in _graphics_native
# Note: Component, Entity are in _entity_native module, imported at runtime
nanobind_add_module(_native
    termin/bindings.cpp
    termin/bindings/render/render_module.cpp
    termin/bindings/render/shader.cpp
    termin/bindings/render/shader_parser.cpp
    termin/bindings/render/camera.cpp
    termin/bindings/render/shadow.cpp
    termin/bindings/render/resource_spec.cpp
    termin/bindings/render/immediate.cpp
    termin/bindings/render/wireframe.cpp
    termin/bindings/render/frame_pass.cpp
    termin/bindings/render/tc_pass_bindings.cpp
    termin/bindings/render/tc_render_surface_bindings.cpp
    termin/bindings/render/tc_input_manager_bindings.cpp
    termin/bindings/render/tc_display_bindings.cpp
    termin/bindings/input/simple_display_input_manager_bindings.cpp
    termin/bindings/render/render_pipeline_bindings.cpp
    termin/bindings/render/material.cpp
    termin/bindings/render/drawable.cpp
    termin/bindings/render/renderers.cpp
    termin/bindings/render/solid_primitive.cpp
    termin/bindings/render/render_engine.cpp
    termin/sdl_bindings.cpp
    termin/platform/sdl_render_surface.cpp
    termin/tc_scene_bindings.cpp
    termin/tc_scene_lighting_bindings.cpp
    # tc_viewport_bindings.cpp moved to _viewport_native module
    termin/tc_component_python.cpp
    termin/tc_component_python_bindings.cpp
    termin/profiler_bindings.cpp
    termin/skeleton_bindings.cpp
    termin/inspect_bindings.cpp
    termin/log_bindings.cpp
    termin/kind_bindings.cpp
    termin/assets/assets_bindings.cpp
    termin/assets/handles.cpp
    termin/render/shader_parser.cpp
    termin/render/shadow_camera.cpp
    termin/render/immediate_renderer.cpp
    termin/render/wireframe_renderer.cpp
    termin/render/solid_primitive_renderer.cpp
    termin/render/glsl_preprocessor.cpp
    termin/texture/tc_texture_handle.cpp
    termin/render/skinned_mesh_renderer.cpp
    termin/render/fbo_pool.cpp
    termin/render/render_engine.cpp
    termin/render/color_pass.cpp
    termin/render/depth_pass.cpp
    termin/render/normal_pass.cpp
    termin/render/shadow_pass.cpp
    termin/render/id_pass.cpp
    termin/render/glad/src/glad.c
)
target_include_directories(_native PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/termin/render/glad/include
    ${SDL2_INCLUDE_DIRS}
)
target_link_libraries(_native PRIVATE OpenGL::GL ${SDL2_LIBRARIES} trent entity_lib skeleton_lib navmesh_lib render_lib)

if(UNIX AND NOT APPLE)
    target_link_libraries(_native PRIVATE ${CMAKE_DL_LIBS})
endif()
target_compile_definitions(_native PRIVATE TERMIN_HAS_NANOBIND)
target_compile_options(_native PRIVATE
    $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
)
# Exclude glad.c from precompiled headers (it's C, not C++)
set_source_files_properties(termin/render/glad/src/glad.c PROPERTIES SKIP_PRECOMPILE_HEADERS ON)

# ---------------- Tests ----------------
option(BUILD_TESTS "Build C++ tests" OFF)

if(BUILD_TESTS)
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
        tests/tests_colliders.cpp
        tests/tests_collision.cpp
    )
    target_include_directories(termin_tests PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/tests
    )
    target_link_libraries(termin_tests PRIVATE entity_lib)
    target_compile_options(termin_tests PRIVATE
        $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
    )
    add_test(NAME termin_tests COMMAND ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin_tests${CMAKE_EXECUTABLE_SUFFIX})

    # Nanobind module to run C++ tests from Python
    nanobind_add_module(_cpp_tests
        tests/tests_binding.cpp
        tests/tests_general_pose3.cpp
        tests/tests_colliders.cpp
        tests/tests_collision.cpp
    )
    target_include_directories(_cpp_tests PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/tests
    )
    target_link_libraries(_cpp_tests PRIVATE entity_lib)
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
endif()

# Install to python packages
# Install shared libraries to root termin directory
install(TARGETS trent entity_lib termin_core
    RUNTIME DESTINATION ${CMAKE_INSTALL_PREFIX}  # .dll on Windows
    LIBRARY DESTINATION ${CMAKE_INSTALL_PREFIX}  # .so on Linux
    ARCHIVE DESTINATION ${CMAKE_INSTALL_PREFIX}/lib  # .lib import libraries on Windows
)

# Set RPATH for shared libraries to find each other in the same directory
set_target_properties(entity_lib PROPERTIES
    INSTALL_RPATH "$ORIGIN"
    BUILD_WITH_INSTALL_RPATH TRUE
)

# Set RPATH for all modules that depend on entity_lib/trent
# Modules in subdirectories need $ORIGIN/.. to find libs in parent (termin/)
set_target_properties(_geom_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_colliders_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_physics_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_voxels_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_collision_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_lighting_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_texture_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_graphics_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_mesh_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_skeleton_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_viewport_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_entity_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_animation_native PROPERTIES
    INSTALL_RPATH "$ORIGIN/../.."
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_navmesh_native PROPERTIES
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
install(TARGETS _navmesh_native DESTINATION ${CMAKE_INSTALL_PREFIX}/navmesh)
install(TARGETS _lighting_native DESTINATION ${CMAKE_INSTALL_PREFIX}/lighting)
install(TARGETS _mesh_native DESTINATION ${CMAKE_INSTALL_PREFIX}/mesh)
install(TARGETS _skeleton_native DESTINATION ${CMAKE_INSTALL_PREFIX}/skeleton)
install(TARGETS _texture_native DESTINATION ${CMAKE_INSTALL_PREFIX}/texture)
install(TARGETS _graphics_native DESTINATION ${CMAKE_INSTALL_PREFIX}/graphics)
install(TARGETS _viewport_native DESTINATION ${CMAKE_INSTALL_PREFIX}/viewport)
install(TARGETS _entity_native DESTINATION ${CMAKE_INSTALL_PREFIX}/entity)
install(TARGETS _native DESTINATION ${CMAKE_INSTALL_PREFIX})

# ============== C# SWIG Bindings ==============
option(BUILD_CSHARP_BINDINGS "Build C# SWIG bindings (termin.dll)" OFF)

if(BUILD_CSHARP_BINDINGS)
    # SWIG wrapper library for C# bindings
    # This creates termin.dll that C# P/Invoke calls
    add_library(termin SHARED
        ${CMAKE_CURRENT_SOURCE_DIR}/../csharp/termin_wrap.cxx
        termin/render/opengl/tc_opengl.cpp
        termin/render/glad/src/glad.c
    )
    target_include_directories(termin PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/../core_c/include
        ${CMAKE_CURRENT_SOURCE_DIR}/termin/render/glad/include
    )
    # Link render_lib with whole-archive to include static pass registrations
    add_dependencies(termin render_lib)
    if(MSVC)
        target_link_libraries(termin PRIVATE
            OpenGL::GL
            termin_core
            trent
            entity_lib
            -WHOLEARCHIVE:$<TARGET_FILE:render_lib>
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
        # Export all symbols on Windows
        set_target_properties(termin PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)
    endif()
    target_compile_options(termin PRIVATE
        $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>
    )
    install(TARGETS termin
        RUNTIME DESTINATION ${CMAKE_INSTALL_PREFIX}/../csharp/Termin.Native/runtimes/win-x64/native
        LIBRARY DESTINATION ${CMAKE_INSTALL_PREFIX}/../csharp/Termin.Native/runtimes/linux-x64/native
    )
endif()
