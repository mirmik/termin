# Python bindings using nanobind
# This file is only included when NOT building C# bindings

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

# ============== Small utility modules ==============

# Geom native module (Vec3, Quat, Pose3, Screw3, GeneralPose3, Transform, AABB)
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
target_compile_options(_geom_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
target_link_libraries(_geom_native PRIVATE entity_lib)

# Colliders native module (BoxCollider, SphereCollider)
nanobind_add_module(_colliders_native termin/colliders_bindings.cpp)
target_link_libraries(_colliders_native PRIVATE entity_lib)
target_compile_options(_colliders_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)

# Physics native module (RigidBody, PhysicsWorld, Contact)
nanobind_add_module(_physics_native termin/physics_bindings.cpp)
target_link_libraries(_physics_native PRIVATE entity_lib)
target_compile_options(_physics_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)

# Voxels native module (VoxelGrid, voxelization, VoxelGridHandle)
nanobind_add_module(_voxels_native termin/voxels_bindings.cpp)
target_compile_options(_voxels_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
target_link_libraries(_voxels_native PRIVATE entity_lib trent)

# Collision native module (BVH, CollisionWorld, ContactManifold)
nanobind_add_module(_collision_native termin/collision_bindings.cpp)
target_link_libraries(_collision_native PRIVATE entity_lib)
target_compile_options(_collision_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)

# Lighting native module (Light, AttenuationCoefficients, LightComponent)
nanobind_add_module(_lighting_native termin/lighting_bindings.cpp)
target_link_libraries(_lighting_native PRIVATE entity_lib)
target_compile_options(_lighting_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)

# Skeleton native module (Bone, SkeletonData, SkeletonInstance, SkeletonController)
nanobind_add_module(_skeleton_native
    termin/bindings/skeleton/skeleton_module.cpp
)
target_link_libraries(_skeleton_native PRIVATE trent entity_lib skeleton_lib)
target_compile_options(_skeleton_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)

# ============== Core entity/viewport modules ==============

# Viewport native module (TcViewport)
nanobind_add_module(_viewport_native
    termin/bindings/viewport/viewport_module.cpp
)
target_link_libraries(_viewport_native PRIVATE entity_lib)
target_compile_definitions(_viewport_native PRIVATE TERMIN_HAS_NANOBIND)
target_compile_options(_viewport_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)

# Entity native module (Component, Entity, Scene, registries)
nanobind_add_module(_entity_native
    termin/bindings/entity/entity_module.cpp
    termin/bindings/entity/entity_bindings.cpp
    termin/bindings/camera/camera_bindings.cpp
    termin/bindings/camera/orbit_camera_bindings.cpp
    termin/bindings/colliders/collider_bindings.cpp
    termin/bindings/input/input_events_bindings.cpp
    termin/tc_scene.cpp
    termin/tc_scene_bindings.cpp
    termin/tc_scene_lighting_bindings.cpp
)
target_link_libraries(_entity_native PRIVATE entity_lib trent render_lib)
target_compile_definitions(_entity_native PRIVATE TERMIN_HAS_NANOBIND)
target_compile_options(_entity_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)

# Animation native module (TcAnimationClip, AnimationPlayer)
nanobind_add_module(_animation_native
    termin/bindings/animation/animation_module.cpp
    termin/animation/animation_player.cpp
)
target_link_libraries(_animation_native PRIVATE trent entity_lib skeleton_lib)
target_compile_options(_animation_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)

# NavMesh native module (RecastNavMeshBuilderComponent)
nanobind_add_module(_navmesh_native
    termin/bindings/navmesh/navmesh_module.cpp
)
target_link_libraries(_navmesh_native PRIVATE trent entity_lib navmesh_lib render_lib)
target_compile_options(_navmesh_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)

# ============== Main unified module ==============

# SDL2 sources (optional)
set(_NATIVE_SDL_SOURCES "")
if(SDL2_FOUND)
    set(_NATIVE_SDL_SOURCES
        termin/sdl_bindings.cpp
        termin/platform/sdl_render_surface.cpp
    )
endif()

nanobind_add_module(_native
    termin/bindings.cpp
    termin/bindings/render/render_module.cpp
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
    termin/bindings/input/display_input_router_bindings.cpp
    termin/bindings/render/render_pipeline_bindings.cpp
    termin/bindings/render/scene_pipeline_template_bindings.cpp
    termin/bindings/render/material.cpp
    termin/bindings/render/drawable.cpp
    termin/bindings/render/renderers.cpp
    termin/bindings/render/solid_primitive.cpp
    termin/bindings/render/render_engine.cpp
    termin/bindings/render/rendering_manager_bindings.cpp
    termin/bindings/editor/gizmo_bindings.cpp
    termin/bindings/editor/editor_interaction_bindings.cpp
    termin/bindings/editor/frame_graph_debugger_bindings.cpp
    termin/editor/frame_graph_debugger_core.cpp
    termin/editor/gizmo_manager.cpp
    termin/editor/transform_gizmo.cpp
    termin/editor/editor_viewport_input_manager.cpp
    termin/editor/editor_interaction_system.cpp
    ${_NATIVE_SDL_SOURCES}
    termin/scene/scene_manager_bindings.cpp
    termin/engine/engine_core.cpp
    termin/bindings/engine/engine_core_bindings.cpp
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
    termin/render/skinned_mesh_renderer.cpp
    termin/render/fbo_pool.cpp
    termin/render/render_engine.cpp
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
)
target_link_libraries(_native PRIVATE OpenGL::GL trent entity_lib skeleton_lib navmesh_lib render_lib tgfx::termin_graphics)

if(SDL2_FOUND)
    target_include_directories(_native PRIVATE ${SDL2_INCLUDE_DIRS})
    target_link_libraries(_native PRIVATE ${SDL2_LIBRARIES})
    target_compile_definitions(_native PRIVATE TERMIN_HAS_SDL2)
endif()

if(UNIX AND NOT APPLE)
    target_link_libraries(_native PRIVATE ${CMAKE_DL_LIBS})
endif()
target_compile_definitions(_native PRIVATE TERMIN_HAS_NANOBIND)
target_compile_options(_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
set_target_properties(_native PROPERTIES
    INSTALL_RPATH "$ORIGIN"
    BUILD_WITH_INSTALL_RPATH TRUE
)
# ============== Tests module ==============

if(BUILD_TESTS)
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
    target_compile_options(_cpp_tests PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
    install(TARGETS _cpp_tests DESTINATION ${TERMIN_PYTHON_PREFIX}/tests)
endif()

# ============== RPATH settings ==============

set_target_properties(entity_lib PROPERTIES
    INSTALL_RPATH "$ORIGIN"
    BUILD_WITH_INSTALL_RPATH TRUE
)
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

# ============== Install targets ==============

install(TARGETS _geom_native DESTINATION ${TERMIN_PYTHON_PREFIX}/geombase)
install(TARGETS _colliders_native DESTINATION ${TERMIN_PYTHON_PREFIX}/colliders)
install(TARGETS _physics_native DESTINATION ${TERMIN_PYTHON_PREFIX}/physics)
install(TARGETS _voxels_native DESTINATION ${TERMIN_PYTHON_PREFIX}/voxels)
install(TARGETS _collision_native DESTINATION ${TERMIN_PYTHON_PREFIX}/collision)
install(TARGETS _animation_native DESTINATION ${TERMIN_PYTHON_PREFIX}/visualization/animation)
install(TARGETS _navmesh_native DESTINATION ${TERMIN_PYTHON_PREFIX}/navmesh)
install(TARGETS _lighting_native DESTINATION ${TERMIN_PYTHON_PREFIX}/lighting)
install(TARGETS _skeleton_native DESTINATION ${TERMIN_PYTHON_PREFIX}/skeleton)
install(TARGETS _viewport_native DESTINATION ${TERMIN_PYTHON_PREFIX}/viewport)
install(TARGETS _entity_native DESTINATION ${TERMIN_PYTHON_PREFIX}/entity)
install(TARGETS _native DESTINATION ${TERMIN_PYTHON_PREFIX})
