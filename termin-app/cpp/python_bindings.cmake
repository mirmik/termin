# Python bindings using nanobind
# This file is only included when NOT building C# bindings

find_package(nanobind CONFIG REQUIRED)

# ============== Small utility modules ==============

# Voxels native module (VoxelGrid, voxelization, VoxelGridHandle)
nanobind_add_module(_voxels_native NB_SHARED termin/voxels_bindings.cpp)
target_compile_options(_voxels_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
target_link_libraries(_voxels_native PRIVATE entity_lib trent)

# _lighting_native has been extracted into the standalone termin-lighting subproject.
# See termin-env/termin-lighting/ — it is built by build-sdk-bindings.sh after main termin.

# ============== Core entity modules ==============

# Entity native module (Component, Entity, Scene, registries)
nanobind_add_module(_entity_native NB_SHARED
    termin/bindings/entity/entity_module.cpp
    termin/bindings/camera/orbit_camera_bindings.cpp
    termin/bindings/input/input_events_bindings.cpp
    termin/tc_scene_bindings.cpp
    termin/tc_scene_lighting_bindings.cpp
)
target_link_libraries(_entity_native PRIVATE entity_lib trent render_lib)
target_compile_definitions(_entity_native PRIVATE TERMIN_HAS_NANOBIND)
target_compile_options(_entity_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)

if(TERMIN_HAS_RECAST)
    # NavMesh native module (RecastNavMeshBuilderComponent)
    nanobind_add_module(_navmesh_native NB_SHARED
        termin/bindings/navmesh/navmesh_module.cpp
    )
    target_link_libraries(_navmesh_native PRIVATE trent entity_lib navmesh_lib render_lib)
    target_compile_options(_navmesh_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
endif()

# ============== Main unified module ==============

# SDL platform bindings moved to termin-display/_platform_native

nanobind_add_module(_native NB_SHARED
    # Python bindings entry point + per-subsystem registration files.
    # The actual C++ pass / renderer implementations live in render_lib —
    # linking PUBLIC against render_lib below pulls their symbols in
    # without compiling them a second time here. Listing them in both
    # lists used to cause duplicate symbols (one copy in render_lib, one
    # in _native.so) and led to silent "my latest changes aren't visible"
    # bugs because the linker picked the local copy from _native.
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
    termin/bindings/render/material.cpp
    termin/bindings/render/drawable.cpp
    termin/bindings/render/renderers.cpp
    termin/bindings/render/solid_primitive.cpp
    termin/bindings/render/render_engine.cpp
    termin/bindings/editor/gizmo_bindings.cpp
    termin/bindings/editor/editor_interaction_bindings.cpp
    termin/bindings/editor/frame_graph_debugger_bindings.cpp
    termin/editor/gizmo_manager.cpp
    termin/editor/transform_gizmo.cpp
    termin/editor/editor_viewport_input_manager.cpp
    termin/editor/editor_interaction_system.cpp
    termin/bindings/modules/term_modules_integration_bindings.cpp
    termin/tc_component_python.cpp
    termin/tc_component_python_bindings.cpp
    termin/profiler_bindings.cpp
    termin/skeleton_bindings.cpp
    termin/inspect_bindings.cpp
    termin/kind_bindings.cpp
    termin/assets/assets_bindings.cpp
    termin/assets/handles.cpp

    # Renderer sources unique to _native (NOT in RENDER_LIB_SOURCES).
    # Keep this list tight — every file here compiled twice = duplicate symbols.
    termin/render/immediate_renderer.cpp
    termin/render/solid_primitive_renderer.cpp
    termin/render/skinned_mesh_renderer.cpp
)
target_link_libraries(_native PRIVATE
    OpenGL::GL
    trent
    entity_lib
    termin_inspect::termin_inspect_python
    termin_skeleton::termin_skeleton
    termin_components_skeleton::termin_components_skeleton
    render_lib
    tgfx::termin_graphics
)
if(TERMIN_HAS_RECAST)
    target_link_libraries(_native PRIVATE navmesh_lib)
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
    nanobind_add_module(_cpp_tests NB_SHARED
        tests/tests_binding.cpp
        tests/tests_general_pose3.cpp
    )
    target_include_directories(_cpp_tests PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/tests
    )
    target_link_libraries(_cpp_tests PRIVATE entity_lib)
    target_compile_options(_cpp_tests PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
    install(TARGETS _cpp_tests DESTINATION ${TERMIN_PYTHON_INSTALL_DIR}/tests)
endif()

# ============== RPATH settings ==============

# Ensure native Python modules can find bundled libs in SDK lib dir
# by walking up from package subdirs.
set(TERMIN_PY_RPATH "$ORIGIN;$ORIGIN/..;$ORIGIN/../..;$ORIGIN/../../..;${CMAKE_INSTALL_PREFIX}/lib")

set_target_properties(entity_lib PROPERTIES
    INSTALL_RPATH "${TERMIN_PY_RPATH}"
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_voxels_native PROPERTIES
    INSTALL_RPATH "${TERMIN_PY_RPATH}"
    BUILD_WITH_INSTALL_RPATH TRUE
)
set_target_properties(_entity_native PROPERTIES
    INSTALL_RPATH "${TERMIN_PY_RPATH}"
    BUILD_WITH_INSTALL_RPATH TRUE
)
if(TERMIN_HAS_RECAST)
    set_target_properties(_navmesh_native PROPERTIES
        INSTALL_RPATH "${TERMIN_PY_RPATH}"
        BUILD_WITH_INSTALL_RPATH TRUE
    )
endif()
set_target_properties(_native PROPERTIES
    INSTALL_RPATH "${TERMIN_PY_RPATH}"
    BUILD_WITH_INSTALL_RPATH TRUE
)

# ============== Install targets ==============

install(TARGETS _voxels_native DESTINATION ${TERMIN_PYTHON_INSTALL_DIR}/voxels)
if(TERMIN_HAS_RECAST)
    install(TARGETS _navmesh_native DESTINATION ${TERMIN_PYTHON_INSTALL_DIR}/navmesh)
endif()
install(TARGETS _entity_native DESTINATION ${TERMIN_PYTHON_INSTALL_DIR}/entity)
install(TARGETS _native DESTINATION ${TERMIN_PYTHON_INSTALL_DIR})
