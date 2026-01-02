#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include "termin/mesh_bindings.hpp"
#include "termin/mesh/tc_mesh_handle.hpp"
#include "termin/inspect/inspect_registry.hpp"
#include "../../../../core_c/include/tc_kind.hpp"
#include "tc_log.hpp"

namespace nb = nanobind;

namespace {

void register_tc_mesh_kind() {
    // C++ handler for tc_mesh kind
    tc::KindRegistry::instance().register_cpp("tc_mesh",
        // serialize: std::any(TcMesh) → trent
        [](const std::any& value) -> nos::trent {
            const termin::TcMesh& m = std::any_cast<const termin::TcMesh&>(value);
            nos::trent result;
            result.init(nos::trent_type::dict);
            if (m.is_valid()) {
                result["uuid"] = std::string(m.uuid());
                result["name"] = std::string(m.name());
            }
            return result;
        },
        // deserialize: trent, scene → std::any(TcMesh)
        [](const nos::trent& t, tc_scene*) -> std::any {
            if (!t.is_dict()) return termin::TcMesh();
            auto& dict = t.as_dict();
            auto it = dict.find("uuid");
            if (it == dict.end() || !it->second.is_string()) {
                return termin::TcMesh();
            }
            std::string uuid = it->second.as_string();
            termin::TcMesh mesh = termin::TcMesh::from_uuid(uuid);
            if (!mesh.is_valid()) {
                auto name_it = dict.find("name");
                std::string name = (name_it != dict.end() && name_it->second.is_string())
                    ? name_it->second.as_string() : "";
                tc::Log::warn("tc_mesh deserialize: mesh not found, uuid=%s name=%s", uuid.c_str(), name.c_str());
            }
            return mesh;
        },
        // to_python: std::any(TcMesh) → nb::object
        [](const std::any& value) -> nb::object {
            return nb::cast(std::any_cast<const termin::TcMesh&>(value));
        },
        // from_python: nb::object → std::any(TcMesh)
        [](nb::object value) -> std::any {
            return nb::cast<termin::TcMesh>(value);
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
            }
            return nb::cast(mesh);
        }),
        // convert
        nb::cpp_function([](nb::object value) -> nb::object {
            if (value.is_none()) {
                return nb::cast(termin::TcMesh());
            }
            if (nb::isinstance<termin::TcMesh>(value)) {
                return value;
            }
            // Try MeshAsset (has 'mesh_data' attribute returning TcMesh)
            if (nb::hasattr(value, "mesh_data")) {
                nb::object res = value.attr("mesh_data");
                if (nb::isinstance<termin::TcMesh>(res)) {
                    return res;
                }
            }
            // Try string (lookup by name)
            if (nb::isinstance<nb::str>(value)) {
                std::string name = nb::cast<std::string>(value);
                tc_mesh_handle h = tc_mesh_find_by_name(name.c_str());
                if (!tc_mesh_handle_is_invalid(h)) {
                    return nb::cast(termin::TcMesh(h));
                }
            }
            tc::Log::error("tc_mesh convert failed: cannot convert to TcMesh");
            return nb::cast(termin::TcMesh());
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
