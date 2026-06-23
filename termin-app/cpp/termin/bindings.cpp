#include <nanobind/nanobind.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

extern "C" {
#include "tc_project_settings.h"
}

#include "render_bindings.hpp"
#include "skeleton_bindings.hpp"
#include "inspect_bindings.hpp"
#include "tc_component_python_bindings.hpp"
#include "assets/assets_bindings.hpp"

// For register_tc_mesh_kind
#include "tgfx/tgfx_mesh_handle.hpp"
#include "termin/inspect/tc_kind.hpp"
#include <tcbase/tc_log.hpp>

namespace nb = nanobind;

namespace termin {
void bind_gizmo(nb::module_& m);
void bind_editor_interaction(nb::module_& m);
void bind_frame_graph_debugger(nb::module_& m);
}

// Entity domain bindings (migrated from _entity_native)
void bind_entity_domain(nb::module_& m);

// Moved from mesh_module.cpp — registers tc_mesh kind handlers for InspectRegistry
static void register_tc_mesh_kind() {
    // C++ handler for tc_mesh kind
    tc::KindRegistry::instance().register_cpp("tc_mesh",
        // serialize: std::any(TcMesh) → tc_value
        [](const std::any& value) -> tc_value {
            const termin::TcMesh& m = std::any_cast<const termin::TcMesh&>(value);
            tc_value result = tc_value_dict_new();
            if (m.is_valid()) {
                tc_value_dict_set(&result, "uuid", tc_value_string(m.uuid()));
                tc_value_dict_set(&result, "name", tc_value_string(m.name()));
            }
            return result;
        },
        // deserialize: tc_value, scene → std::any(TcMesh)
        [](const tc_value* v, void*) -> std::any {
            if (!v || v->type != TC_VALUE_DICT) return termin::TcMesh();
            tc_value* uuid_val = tc_value_dict_get(const_cast<tc_value*>(v), "uuid");
            if (!uuid_val || uuid_val->type != TC_VALUE_STRING || !uuid_val->data.s) {
                return termin::TcMesh();
            }
            std::string uuid = uuid_val->data.s;
            termin::TcMesh mesh = termin::TcMesh::from_uuid(uuid);
            if (!mesh.is_valid()) {
                tc_value* name_val = tc_value_dict_get(const_cast<tc_value*>(v), "name");
                std::string name = (name_val && name_val->type == TC_VALUE_STRING && name_val->data.s)
                    ? name_val->data.s : "";
                tc::Log::warn("tc_mesh deserialize: mesh not found, uuid=%s name=%s", uuid.c_str(), name.c_str());
            } else {
                mesh.ensure_loaded();
            }
            return mesh;
        }
    );

    // Register TcMesh Python type → "tc_mesh" kind mapping
    tc::KindRegistry::instance().register_type(nb::type<termin::TcMesh>(), "tc_mesh");

    // Python handler for tc_mesh kind
    tc::KindRegistry::instance().register_python("tc_mesh",
        // serialize
        nb::cpp_function([](nb::object obj) -> nb::object {
            termin::TcMesh mesh = nb::cast<termin::TcMesh>(obj);
            nb::dict d;
            if (mesh.is_valid()) {
                d["uuid"] = nb::str(mesh.uuid());
                d["name"] = nb::str(mesh.name());
            }
            return d;
        }),
        // deserialize
        nb::cpp_function([](nb::object data) -> nb::object {
            if (!nb::isinstance<nb::dict>(data)) {
                return nb::cast(termin::TcMesh());
            }
            nb::dict d = nb::cast<nb::dict>(data);
            if (!d.contains("uuid")) {
                return nb::cast(termin::TcMesh());
            }
            std::string uuid = nb::cast<std::string>(d["uuid"]);
            termin::TcMesh mesh = termin::TcMesh::from_uuid(uuid);
            if (!mesh.is_valid()) {
                std::string name = d.contains("name") ? nb::cast<std::string>(d["name"]) : "";
                tc::Log::warn("tc_mesh deserialize: mesh not found, uuid=%s name=%s", uuid.c_str(), name.c_str());
            } else {
                mesh.ensure_loaded();
            }
            return nb::cast(mesh);
        })
    );
}

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

    // Termin-specific: RenderSyncMode (from tc_project_settings.h)
    nb::enum_<tc_render_sync_mode>(m, "RenderSyncMode")
        .value("NONE", TC_RENDER_SYNC_NONE)
        .value("FLUSH", TC_RENDER_SYNC_FLUSH)
        .value("FINISH", TC_RENDER_SYNC_FINISH);

    m.def("get_render_sync_mode", []() {
        return tc_project_settings_get_render_sync_mode();
    }, "Get render sync mode between passes");

    m.def("set_render_sync_mode", [](tc_render_sync_mode mode) {
        tc_project_settings_set_render_sync_mode(mode);
    }, nb::arg("mode"), "Set render sync mode between passes");

    // Register tc_mesh kind handler for InspectRegistry (moved from _mesh_native)
    register_tc_mesh_kind();

    auto render_module = m.def_submodule("render", "Render module");
    // SDL platform bindings moved to termin-display/_platform_native
    auto scene_module = m.def_submodule("scene", "Scene module");
    auto modules_module = m.def_submodule("modules", "Modules integration");
    auto skeleton_module = m.def_submodule("skeleton", "Skeleton module");
    // log_module removed — log is imported from tcbase
    auto component_module = m.def_submodule("component", "Component module");
    auto assets_module = m.def_submodule("assets", "Assets module");
    auto editor_module = m.def_submodule("editor", "Editor module");

    termin::bind_render(render_module);
    termin::bind_gizmo(editor_module);
    termin::bind_editor_interaction(editor_module);
    termin::bind_frame_graph_debugger(editor_module);
    nb::module_ engine_native = nb::module_::import_("termin.engine._engine_native");
    modules_module.attr("TermModulesIntegration") =
        engine_native.attr("modules").attr("TermModulesIntegration");
    termin::bind_skeleton(skeleton_module);
    termin::init_domain_inspect();
    // Import log and profiler from tcbase instead of keeping local bindings
    nb::module_ tcbase = nb::module_::import_("tcbase._tcbase_native");
    m.attr("log") = tcbase.attr("log");
    m.attr("profiler") = tcbase.attr("profiler");

    // TcComponent is registered in _scene_native — re-export it
    nb::module_ scene_native = nb::module_::import_("termin.scene._scene_native");
    component_module.attr("TcComponent") = scene_native.attr("TcComponent");
    // Initialize termin-specific drawable and input callbacks
    termin::init_python_component_callbacks();

    termin::bind_assets(assets_module);

    // Register cleanup function to be called before Python shutdown
    m.def("_cleanup_python_objects", []() {},
        "Internal: cleanup all Python objects stored in C++ before shutdown");

    // Register cleanup with Python's atexit module
    nb::module_ atexit = nb::module_::import_("atexit");
    atexit.attr("register")(nb::cpp_function([]() {}));
}
