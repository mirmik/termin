# Python bindings using nanobind
# This file is only included when NOT building C# bindings

find_package(nanobind CONFIG REQUIRED)

set(TERMIN_APP_EDITOR_NATIVE_SOURCES
    termin/bindings/editor/editor_native_module.cpp
    termin/bindings/editor/gizmo_bindings.cpp
    termin/bindings/editor/editor_interaction_bindings.cpp
    termin/bindings/editor/frame_graph_debugger_bindings.cpp
    termin/bindings/editor/frame_profiler_bindings.cpp
    termin/bindings/render/solid_primitive.cpp
    termin/editor/camera_frustum_debug_gizmo.cpp
    termin/editor/camera_frustum_math.cpp
    termin/editor/component_editor_visual.cpp
    termin/editor/editor_snap.cpp
    termin/editor/gizmo_manager.cpp
    termin/editor/gizmo_types.cpp
    termin/editor/transform_gizmo.cpp
    termin/editor/editor_viewport_input_manager.cpp
    termin/editor/editor_interaction_system.cpp
    termin/editor/frame_profiler_controller.cpp
    termin/editor/selection_manager.cpp
    termin/render/solid_primitive_renderer.cpp
)

if(TERMIN_HAS_RECAST)
    list(APPEND TERMIN_APP_EDITOR_NATIVE_SOURCES
        termin/navmesh/off_mesh_link_editor_visual.cpp
    )
endif()

# SDL platform bindings moved to termin-display/_platform_native

nanobind_add_module(_editor_native NB_SHARED ${TERMIN_APP_EDITOR_NATIVE_SOURCES})
target_link_libraries(_editor_native PRIVATE
    tcbase::termin_base
    termin_scene::termin_scene
    termin_input::termin_input
    termin_collision::termin_collision
    termin_components_collision::termin_components_collision
    termin_components_kinematic::termin_components_kinematic
    termin_components_render::termin_components_render
    termin_render::termin_render
    termin_display::termin_display
    termin_engine::termin_engine
    termin_gui_native::termin_gui_native
    termin_render_passes::termin_render_passes
    tgfx::termin_graphics
    tgfx::termin_graphics2
)
if(TGFX2_ENABLE_OPENGL)
    target_link_libraries(_editor_native PRIVATE OpenGL::GL)
endif()
if(TERMIN_HAS_RECAST)
    target_link_libraries(_editor_native PRIVATE termin_navmesh::termin_navmesh_components)
endif()
if(UNIX AND NOT APPLE)
    target_link_libraries(_editor_native PRIVATE ${CMAKE_DL_LIBS})
endif()
target_compile_definitions(_editor_native PRIVATE TERMIN_HAS_NANOBIND)
target_compile_options(_editor_native PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
set_target_properties(_editor_native PROPERTIES
    INSTALL_RPATH "$ORIGIN;$ORIGIN/.."
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
        termin_scene::termin_scene
    )
    target_compile_options(_cpp_tests PRIVATE $<$<CONFIG:Release>:${OPTIMIZE_FLAGS}>)
    install(TARGETS _cpp_tests DESTINATION ${TERMIN_PYTHON_INSTALL_DIR}/tests)
endif()

# ============== RPATH settings ==============

# Ensure native Python modules can find bundled libs in SDK lib dir
# by walking up from package subdirs.
set(TERMIN_PY_RPATH "$ORIGIN;$ORIGIN/..;$ORIGIN/../..;$ORIGIN/../../..;${CMAKE_INSTALL_PREFIX}/lib")

set_target_properties(_editor_native PROPERTIES
    INSTALL_RPATH "${TERMIN_PY_RPATH}"
    BUILD_WITH_INSTALL_RPATH TRUE
)

# ============== Install targets ==============

install(TARGETS _editor_native DESTINATION ${TERMIN_PYTHON_INSTALL_DIR}/editor)
