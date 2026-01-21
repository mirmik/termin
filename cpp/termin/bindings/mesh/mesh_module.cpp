#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include "termin/mesh_bindings.hpp"
#include "termin/mesh/tc_mesh_handle.hpp"
#include "termin/inspect/tc_kind.hpp"
#include "tc_log.hpp"

namespace nb = nanobind;

namespace {

void register_tc_mesh_kind() {
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
        [](const tc_value* v, tc_scene*) -> std::any {
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
                // Trigger lazy load if mesh is declared but not loaded
                mesh.ensure_loaded();
            }
            return mesh;
        }
    );

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
                // Trigger lazy load if mesh is declared but not loaded
                mesh.ensure_loaded();
            }
            return nb::cast(mesh);
        })
    );
}

} // anonymous namespace

NB_MODULE(_mesh_native, m) {
    m.doc() = "Native C++ mesh module (Mesh3, TcMesh)";

    // Bind Mesh3 (CPU mesh) and TcMesh (GPU-ready mesh in tc_mesh registry)
    termin::bind_mesh(m);

    // Register tc_mesh kind handler for InspectRegistry
    register_tc_mesh_kind();
}
