# Python bindings using nanobind
# This file is only included when NOT building C# bindings

find_package(nanobind CONFIG REQUIRED)

# ============== Main unified module ==============

set(TERMIN_APP_NATIVE_SOURCES
    # Python bindings entry point + per-subsystem registration files.
    termin/bindings.cpp
    termin/bindings/render/render_module.cpp
    termin/bindings/render/camera.cpp
    termin/bindings/render/shadow.cpp
    termin/bindings/render/material.cpp
    termin/bindings/render/solid_primitive.cpp
    termin/bindings/editor/gizmo_bindings.cpp
    termin/bindings/editor/editor_interaction_bindings.cpp
    termin/bindings/editor/frame_graph_debugger_bindings.cpp
    termin/editor/component_editor_visual.cpp
    termin/editor/editor_snap.cpp
    termin/editor/gizmo_manager.cpp
    termin/editor/transform_gizmo.cpp
    termin/editor/editor_viewport_input_manager.cpp
    termin/editor/editor_interaction_system.cpp
    termin/tc_component_python_bindings.cpp
    termin/skeleton_bindings.cpp
    termin/inspect_bindings.cpp
    termin/assets/assets_bindings.cpp
    termin/assets/handles.cpp

    # Renderer sources unique to _native.
    # Keep this list tight — most render implementations live in extracted packages.
    termin/render/solid_primitive_renderer.cpp

    # Entity domain bindings (migrated from _entity_native)
    termin/bindings/entity/entity_native_to_native.cpp
    termin/tc_scene_bindings.cpp
    termin/tc_scene_lighting_bindings.cpp
)

if(TERMIN_HAS_RECAST)
    list(APPEND TERMIN_APP_NATIVE_SOURCES
        termin/navmesh/off_mesh_link_editor_visual.cpp
    )
endif()

# SDL platform bindings moved to termin-display/_platform_native

nanobind_add_module(_native NB_SHARED ${TERMIN_APP_NATIVE_SOURCES})
target_link_libraries(_native PRIVATE
    tcbase::termin_base
    termin_core
    termin_inspect::termin_inspect
    termin_inspect::termin_inspect_python
    termin_scene::termin_scene
    termin_input::termin_input
    termin_collision::termin_collision
    termin_components_collision::termin_components_collision
    termin_components_kinematic::termin_components_kinematic
    termin_components_render::termin_components_render
    termin_render::termin_render
    termin_display::termin_display
    termin_skeleton::termin_skeleton
    termin_components_skeleton::termin_components_skeleton
    termin_voxels::termin_voxels
    termin_engine::termin_engine
    termin_render_passes::termin_render_passes
    tgfx::termin_graphics
    tgfx::termin_graphics2
)
if(TGFX2_ENABLE_OPENGL)
    target_link_libraries(_native PRIVATE OpenGL::GL)
endif()
if(TERMIN_HAS_RECAST)
    target_link_libraries(_native PRIVATE termin_navmesh::termin_navmesh_components)
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
    target_link_libraries(_cpp_tests PRIVATE
        tcbase::termin_base
        termin_core
        termin_scene::termin_scene
    )
    target_compile_options(_cpp_tests PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
    install(TARGETS _cpp_tests DESTINATION ${TERMIN_PYTHON_INSTALL_DIR}/tests)
endif()

# ============== RPATH settings ==============

# Ensure native Python modules can find bundled libs in SDK lib dir
# by walking up from package subdirs.
set(TERMIN_PY_RPATH "$ORIGIN;$ORIGIN/..;$ORIGIN/../..;$ORIGIN/../../..;${CMAKE_INSTALL_PREFIX}/lib")

set_target_properties(_native PROPERTIES
    INSTALL_RPATH "${TERMIN_PY_RPATH}"
    BUILD_WITH_INSTALL_RPATH TRUE
)

# ============== Install targets ==============

install(TARGETS _native DESTINATION ${TERMIN_PYTHON_INSTALL_DIR})
