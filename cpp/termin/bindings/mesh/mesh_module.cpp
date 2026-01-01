#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include "termin/mesh_bindings.hpp"
#include "termin/mesh/tc_mesh_handle.hpp"
#include "termin/assets/handles.hpp"
#include "termin/inspect/inspect_registry.hpp"
#include "../../../../core_c/include/tc_kind.hpp"
#include "tc_log.hpp"

namespace nb = nanobind;

namespace {

void bind_mesh_handle(nb::module_& m) {
    nb::class_<termin::MeshHandle>(m, "MeshHandle")
        .def(nb::init<>())
        .def("__init__", [](termin::MeshHandle* self, nb::object asset) {
            new (self) termin::MeshHandle(asset);
        }, nb::arg("asset"))
        .def_static("from_name", &termin::MeshHandle::from_name, nb::arg("name"))
        .def_static("from_asset", &termin::MeshHandle::from_asset, nb::arg("asset"))
        .def_static("from_direct", &termin::MeshHandle::from_direct, nb::arg("mesh"),
            nb::rv_policy::reference)
        .def_static("from_mesh3", &termin::MeshHandle::from_mesh3,
            nb::arg("mesh"), nb::arg("name") = "mesh", nb::arg("source_path") = "")
        .def_static("from_mesh", &termin::MeshHandle::from_mesh3,  // alias
            nb::arg("mesh"), nb::arg("name") = "mesh", nb::arg("source_path") = "")
        .def_static("from_vertices_indices", &termin::MeshHandle::from_vertices_indices,
            nb::arg("vertices"), nb::arg("indices"), nb::arg("name") = "mesh")
        .def_static("deserialize", &termin::MeshHandle::deserialize, nb::arg("data"))
        .def_rw("_direct", &termin::MeshHandle::_direct)
        .def_rw("asset", &termin::MeshHandle::asset)
        .def_prop_ro("is_valid", &termin::MeshHandle::is_valid)
        .def_prop_ro("is_direct", &termin::MeshHandle::is_direct)
        .def_prop_ro("name", &termin::MeshHandle::name)
        .def_prop_ro("version", &termin::MeshHandle::version)
        .def_prop_ro("mesh", &termin::MeshHandle::mesh)
        .def_prop_ro("gpu", &termin::MeshHandle::gpu, nb::rv_policy::reference)
        .def("get", &termin::MeshHandle::get, nb::rv_policy::reference)
        .def("get_mesh", &termin::MeshHandle::mesh)
        .def("get_mesh_or_none", &termin::MeshHandle::mesh)
        .def("get_asset", [](const termin::MeshHandle& self) { return self.asset; })
        .def("serialize", &termin::MeshHandle::serialize);
}

void register_mesh_kind() {
    // C++ handler for C++ fields
    tc::register_cpp_handle_kind<termin::MeshHandle>("mesh_handle");

    // Python handler for Python fields
    tc::KindRegistry::instance().register_python(
        "mesh_handle",
        // serialize
        nb::cpp_function([](nb::object obj) -> nb::object {
            termin::MeshHandle handle = nb::cast<termin::MeshHandle>(obj);
            return handle.serialize();
        }),
        // deserialize
        nb::cpp_function([](nb::object data) -> nb::object {
            if (!nb::isinstance<nb::dict>(data)) {
                return nb::cast(termin::MeshHandle());
            }
            nb::dict d = nb::cast<nb::dict>(data);
            return nb::cast(termin::MeshHandle::deserialize(d));
        }),
        // convert
        nb::cpp_function([](nb::object value) -> nb::object {
            if (value.is_none()) {
                return nb::cast(termin::MeshHandle());
            }
            if (nb::isinstance<termin::MeshHandle>(value)) {
                return value;
            }
            // Try TcMesh (GPU-ready mesh)
            if (nb::isinstance<termin::TcMesh>(value)) {
                auto mesh = nb::cast<termin::TcMesh>(value);
                return nb::cast(termin::MeshHandle::from_direct(std::move(mesh)));
            }
            // Try MeshAsset (has 'resource' attribute)
            if (nb::hasattr(value, "resource")) {
                return nb::cast(termin::MeshHandle::from_asset(value));
            }
            // Nothing worked
            nb::str type_str = nb::borrow<nb::str>(value.type().attr("__name__"));
            std::string type_name = nb::cast<std::string>(type_str);
            tc::Log::error("mesh_handle convert failed: cannot convert %s to MeshHandle", type_name.c_str());
            return nb::cast(termin::MeshHandle());
        })
    );
}

void register_tc_mesh_kind() {
    // C++ handler for tc_mesh kind (TcMesh directly, without MeshHandle wrapper)
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
        // deserialize: trent → std::any(TcMesh)
        [](const nos::trent& t) -> std::any {
            if (!t.is_dict()) return termin::TcMesh();
            auto& dict = t.as_dict();
            auto it = dict.find("uuid");
            if (it == dict.end() || !it->second.is_string()) {
                return termin::TcMesh();
            }
            std::string uuid = it->second.as_string();
            return termin::TcMesh::from_uuid(uuid);
        },
        // to_python: std::any(TcMesh) → nb::object
        [](const std::any& value) -> nb::object {
            return nb::cast(std::any_cast<const termin::TcMesh&>(value));
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
            return nb::cast(termin::TcMesh::from_uuid(uuid));
        }),
        // convert
        nb::cpp_function([](nb::object value) -> nb::object {
            if (value.is_none()) {
                return nb::cast(termin::TcMesh());
            }
            if (nb::isinstance<termin::TcMesh>(value)) {
                return value;
            }
            // Try MeshHandle (extract TcMesh from it)
            if (nb::isinstance<termin::MeshHandle>(value)) {
                termin::MeshHandle handle = nb::cast<termin::MeshHandle>(value);
                return nb::cast(handle.get());
            }
            // Try MeshAsset (has 'resource' attribute returning TcMesh)
            if (nb::hasattr(value, "resource")) {
                nb::object res = value.attr("resource");
                if (nb::isinstance<termin::TcMesh>(res)) {
                    return res;
                }
            }
            // Try string (lookup by name)
            if (nb::isinstance<nb::str>(value)) {
                std::string name = nb::cast<std::string>(value);
                tc_mesh* m = tc_mesh_get_by_name(name.c_str());
                if (m) {
                    return nb::cast(termin::TcMesh(m));
                }
            }
            tc::Log::error("tc_mesh convert failed: cannot convert to TcMesh");
            return nb::cast(termin::TcMesh());
        })
    );
}

} // anonymous namespace

NB_MODULE(_mesh_native, m) {
    m.doc() = "Native C++ mesh module (Mesh3, TcMesh, MeshHandle)";

    // Bind Mesh3 (CPU mesh) and TcMesh (GPU-ready mesh in tc_mesh registry)
    termin::bind_mesh(m);

    // Bind MeshHandle
    bind_mesh_handle(m);

    // Register kind handlers for InspectRegistry
    register_mesh_kind();      // mesh_handle kind (for backwards compatibility)
    register_tc_mesh_kind();   // tc_mesh kind (new, direct TcMesh)
}
