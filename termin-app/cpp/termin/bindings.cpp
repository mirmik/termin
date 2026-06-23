#include <nanobind/nanobind.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "tc_component_python_bindings.hpp"

namespace nb = nanobind;

// Entity domain bindings (migrated from _entity_native)
void bind_entity_domain(nb::module_& m);

NB_MODULE(_native, m) {
    nb::set_leak_warnings(false);
    m.doc() = "Native C++ module for termin";

    // Import tgfx for shared types (Color4, Size2i, TcShader, TcTexture, TcMesh, etc.)
    nb::module_ tgfx = nb::module_::import_("tgfx._tgfx_native");
    m.attr("tgfx") = tgfx;

    // Re-export tgfx as graphics/mesh submodules for backward compatibility
    m.attr("graphics") = tgfx;
    m.attr("mesh") = tgfx;

    // Import _geom_native for Vec3, Mat44 types (used by Material::color, etc.)
    nb::module_ geom_native = nb::module_::import_("tcbase._geom_native");
    m.attr("geom") = geom_native;

    // Import _viewport_native for TcViewport type (used by CameraComponent)
    nb::module_ viewport_native = nb::module_::import_("termin.viewport._viewport_native");
    m.attr("viewport") = viewport_native;

    // Entity domain bindings (migrated from _entity_native)
    bind_entity_domain(m);

    auto render_module = m.def_submodule("render", "Render module");
    auto modules_module = m.def_submodule("modules", "Modules integration");
    auto component_module = m.def_submodule("component", "Component module");
    auto editor_module = m.def_submodule("editor", "Editor module");

    nb::module_ render_components = nb::module_::import_("termin.render_components");
    const char* render_component_exports[] = {
        "Camera",
        "CameraProjection",
    };
    for (const char* name : render_component_exports) {
        render_module.attr(name) = render_components.attr(name);
    }
    nb::module_ render_passes = nb::module_::import_("termin.render_passes");
    const char* render_pass_exports[] = {
        "ShadowCameraParams",
        "build_shadow_projection_matrix",
        "build_shadow_view_matrix",
        "compute_frustum_corners",
        "compute_light_space_matrix",
        "fit_shadow_frustum_to_camera",
    };
    for (const char* name : render_pass_exports) {
        render_module.attr(name) = render_passes.attr(name);
    }
    nb::module_ editor_native = nb::module_::import_("termin.editor._editor_native");
    const char* editor_exports[] = {
        "EditorInteractionSystem",
        "EditorViewportInputManager",
        "FrameGraphCapture",
        "FrameGraphDebuggerCore",
        "FrameGraphPresenter",
        "Gizmo",
        "GizmoCollider",
        "GizmoHit",
        "GizmoManager",
        "HDRStats",
        "SelectionManager",
        "TextureInfo",
        "TransformElement",
        "TransformGizmo",
    };
    for (const char* name : editor_exports) {
        editor_module.attr(name) = editor_native.attr(name);
    }
    render_module.attr("SolidPrimitiveRenderer") =
        editor_native.attr("SolidPrimitiveRenderer");
    nb::module_ engine_native = nb::module_::import_("termin.engine._engine_native");
    modules_module.attr("TermModulesIntegration") =
        engine_native.attr("modules").attr("TermModulesIntegration");
    // Import log and profiler from tcbase instead of keeping local bindings
    nb::module_ tcbase = nb::module_::import_("tcbase._tcbase_native");
    m.attr("log") = tcbase.attr("log");
    m.attr("profiler") = tcbase.attr("profiler");

    // TcComponent is registered in _scene_native — re-export it
    nb::module_ scene_native = nb::module_::import_("termin.scene._scene_native");
    component_module.attr("TcComponent") = scene_native.attr("TcComponent");
    // Register cleanup function to be called before Python shutdown
    m.def("_cleanup_python_objects", []() {},
        "Internal: cleanup all Python objects stored in C++ before shutdown");

    // Register cleanup with Python's atexit module
    nb::module_ atexit = nb::module_::import_("atexit");
    atexit.attr("register")(nb::cpp_function([]() {}));
}
