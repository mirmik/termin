#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "texture_data.hpp"
#include "handles.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/material.hpp"
#include "termin/skeleton/skeleton_data.hpp"
#include "termin/inspect/inspect_registry.hpp"
#include "termin/entity/entity_handle.hpp"
#include "../../../core_c/include/tc_kind.hpp"

namespace py = pybind11;

namespace termin {

// Forward declaration
void register_kind_handlers();

void bind_assets(py::module_& m) {
    // Note: TextureData is now in _texture_native module
    // Note: MeshHandle is now in _mesh_native module

    // ========== TextureHandle ==========
    py::class_<TextureHandle>(m, "TextureHandle")
        .def(py::init<>())
        .def(py::init<py::object>(), py::arg("asset"))
        .def_static("from_name", &TextureHandle::from_name, py::arg("name"))
        .def_static("from_asset", &TextureHandle::from_asset, py::arg("asset"))
        .def_static("from_file", &TextureHandle::from_file,
            py::arg("path"), py::arg("name") = "")
        .def_static("from_texture_data", &TextureHandle::from_texture_data,
            py::arg("texture_data"), py::arg("name") = "texture")
        .def_static("deserialize", &TextureHandle::deserialize, py::arg("data"))
        .def_readwrite("asset", &TextureHandle::asset)
        .def_property_readonly("is_valid", &TextureHandle::is_valid)
        .def_property_readonly("name", &TextureHandle::name)
        .def_property_readonly("version", &TextureHandle::version)
        .def_property_readonly("gpu", &TextureHandle::gpu, py::return_value_policy::reference)
        .def_property_readonly("source_path", &TextureHandle::source_path)
        .def("get", &TextureHandle::get, py::return_value_policy::reference)
        .def("get_asset", [](const TextureHandle& self) { return self.asset; })
        .def("bind", &TextureHandle::bind,
            py::arg("graphics"), py::arg("unit") = 0, py::arg("context_key") = 0)
        .def("serialize", &TextureHandle::serialize);

    // ========== MaterialHandle ==========
    py::class_<MaterialHandle>(m, "MaterialHandle")
        .def(py::init<>())
        .def(py::init<Material*>(), py::arg("material"))
        .def_static("from_direct", &MaterialHandle::from_direct, py::arg("material"),
            py::return_value_policy::reference)
        .def_static("from_material", &MaterialHandle::from_direct, py::arg("material"),
            py::return_value_policy::reference)  // alias for from_direct
        .def_static("from_asset", &MaterialHandle::from_asset, py::arg("asset"))
        .def_static("from_name", &MaterialHandle::from_name, py::arg("name"))
        .def_static("deserialize", &MaterialHandle::deserialize, py::arg("data"))
        .def_readwrite("_direct", &MaterialHandle::_direct)
        .def_readwrite("asset", &MaterialHandle::asset)
        .def_property_readonly("is_valid", &MaterialHandle::is_valid)
        .def_property_readonly("is_direct", &MaterialHandle::is_direct)
        .def_property_readonly("name", &MaterialHandle::name)
        .def_property_readonly("material", &MaterialHandle::get_material_or_none,
            py::return_value_policy::reference)
        .def("get", &MaterialHandle::get, py::return_value_policy::reference)
        .def("get_asset", [](const MaterialHandle& self) { return self.asset; })
        .def("get_material", &MaterialHandle::get_material, py::return_value_policy::reference)
        .def("get_material_or_none", &MaterialHandle::get_material_or_none,
            py::return_value_policy::reference)
        .def("serialize", &MaterialHandle::serialize);

    // Allow implicit conversion from Material (shared_ptr) to MaterialHandle
    py::implicitly_convertible<std::shared_ptr<Material>, MaterialHandle>();
    // Allow implicit conversion from Material* to MaterialHandle
    py::implicitly_convertible<Material*, MaterialHandle>();

    // Note: SkeletonHandle is now in _skeleton_native module

    // ========== Free functions ==========
    m.def("get_white_texture_handle", &get_white_texture_handle,
        "Get a white 1x1 texture handle (singleton).");

    // Register kind handlers for serialization
    register_kind_handlers();
}

void register_kind_handlers() {
    // Note: mesh_handle kind is registered in _mesh_native module

    // ===== material_handle kind =====
    // C++ handler for C++ fields
    tc::register_cpp_handle_kind<MaterialHandle>("material_handle");

    // Python handler for Python fields
    tc::KindRegistry::instance().register_python(
        "material_handle",
        // serialize
        py::cpp_function([](py::object obj) -> py::object {
            MaterialHandle handle = obj.cast<MaterialHandle>();
            return handle.serialize();
        }),
        // deserialize
        py::cpp_function([](py::object data) -> py::object {
            if (data.is_none()) {
                return py::cast(MaterialHandle());
            }
            py::dict d = data.cast<py::dict>();
            return py::cast(MaterialHandle::deserialize(d));
        }),
        // convert
        py::cpp_function([](py::object value) -> py::object {
            if (value.is_none()) {
                return py::cast(MaterialHandle());
            }
            if (py::isinstance<MaterialHandle>(value)) {
                return value;
            }
            return value;
        })
    );

    // Note: skeleton kind is registered in _skeleton_native module

    // ===== entity_handle kind =====
    // C++ handler (EntityHandle serializes to string, not dict)
    tc::KindRegistry::instance().register_cpp(
        "entity_handle",
        // serialize: std::any(EntityHandle) → trent(string)
        [](const std::any& value) -> nos::trent {
            const EntityHandle& h = std::any_cast<const EntityHandle&>(value);
            if (h.uuid.empty()) return nos::trent::nil();
            return nos::trent(h.uuid);
        },
        // deserialize: trent → std::any(EntityHandle)
        [](const nos::trent& t) -> std::any {
            EntityHandle h;
            h.deserialize_from(t);
            return h;
        },
        // to_python: std::any(EntityHandle) → py::object
        [](const std::any& value) -> py::object {
            const EntityHandle& h = std::any_cast<const EntityHandle&>(value);
            return py::cast(h);
        }
    );

    // Python handler
    tc::KindRegistry::instance().register_python(
        "entity_handle",
        // serialize
        py::cpp_function([](py::object obj) -> py::object {
            if (obj.is_none()) {
                return py::none();
            }
            try {
                EntityHandle handle = obj.cast<EntityHandle>();
                if (!handle.uuid.empty()) {
                    return py::str(handle.uuid);
                }
            } catch (const py::cast_error&) {}
            return py::none();
        }),
        // deserialize
        py::cpp_function([](py::object data) -> py::object {
            if (py::isinstance<py::str>(data)) {
                return py::cast(EntityHandle(data.cast<std::string>()));
            }
            return py::cast(EntityHandle());
        }),
        // convert
        py::none()
    );
    // list[entity_handle] is auto-generated by InspectRegistry
}

} // namespace termin
