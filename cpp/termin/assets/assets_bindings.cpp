#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/shared_ptr.h>
#include <nanobind/ndarray.h>

#include "texture_data.hpp"
#include "handles.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/material.hpp"
#include "termin/skeleton/skeleton_data.hpp"
#include "termin/inspect/inspect_registry.hpp"
#include "termin/entity/entity_handle.hpp"
#include "../../../core_c/include/tc_kind.hpp"

namespace nb = nanobind;

namespace termin {

// Forward declaration
void register_kind_handlers();

void bind_assets(nb::module_& m) {
    // Note: TextureData is now in _texture_native module
    // Note: MeshHandle is now in _mesh_native module

    // ========== TextureHandle ==========
    nb::class_<TextureHandle>(m, "TextureHandle")
        .def(nb::init<>())
        .def(nb::init<nb::object>(), nb::arg("asset"))
        .def_static("from_name", &TextureHandle::from_name, nb::arg("name"))
        .def_static("from_asset", &TextureHandle::from_asset, nb::arg("asset"))
        .def_static("from_file", &TextureHandle::from_file,
            nb::arg("path"), nb::arg("name") = "")
        .def_static("from_texture_data", &TextureHandle::from_texture_data,
            nb::arg("texture_data"), nb::arg("name") = "texture")
        .def_static("deserialize", &TextureHandle::deserialize, nb::arg("data"))
        .def_rw("asset", &TextureHandle::asset)
        .def_prop_ro("is_valid", &TextureHandle::is_valid)
        .def_prop_ro("name", &TextureHandle::name)
        .def_prop_ro("version", &TextureHandle::version)
        .def_prop_ro("gpu", &TextureHandle::gpu, nb::rv_policy::reference)
        .def_prop_ro("source_path", &TextureHandle::source_path)
        .def("get", &TextureHandle::get, nb::rv_policy::reference)
        .def("get_asset", [](const TextureHandle& self) { return self.asset; })
        .def("bind", &TextureHandle::bind,
            nb::arg("graphics"), nb::arg("unit") = 0, nb::arg("context_key") = 0)
        .def("serialize", &TextureHandle::serialize);

    // ========== MaterialHandle ==========
    nb::class_<MaterialHandle>(m, "MaterialHandle")
        .def(nb::init<>())
        .def(nb::init<Material*>(), nb::arg("material"))
        .def_static("from_direct", &MaterialHandle::from_direct, nb::arg("material"),
            nb::rv_policy::reference)
        .def_static("from_material", &MaterialHandle::from_direct, nb::arg("material"),
            nb::rv_policy::reference)  // alias for from_direct
        .def_static("from_asset", &MaterialHandle::from_asset, nb::arg("asset"))
        .def_static("from_name", &MaterialHandle::from_name, nb::arg("name"))
        .def_static("deserialize", &MaterialHandle::deserialize, nb::arg("data"))
        .def_rw("_direct", &MaterialHandle::_direct)
        .def_rw("asset", &MaterialHandle::asset)
        .def_prop_ro("is_valid", &MaterialHandle::is_valid)
        .def_prop_ro("is_direct", &MaterialHandle::is_direct)
        .def_prop_ro("name", &MaterialHandle::name)
        .def_prop_ro("material", &MaterialHandle::get_material_or_none,
            nb::rv_policy::reference)
        .def("get", &MaterialHandle::get, nb::rv_policy::reference)
        .def("get_asset", [](const MaterialHandle& self) { return self.asset; })
        .def("get_material", &MaterialHandle::get_material, nb::rv_policy::reference)
        .def("get_material_or_none", &MaterialHandle::get_material_or_none,
            nb::rv_policy::reference)
        .def("serialize", &MaterialHandle::serialize);

    // Note: nanobind doesn't have implicitly_convertible - handle via explicit constructors

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
        nb::cpp_function([](nb::object obj) -> nb::object {
            MaterialHandle handle = nb::cast<MaterialHandle>(obj);
            return handle.serialize();
        }),
        // deserialize
        nb::cpp_function([](nb::object data) -> nb::object {
            if (data.is_none()) {
                return nb::cast(MaterialHandle());
            }
            nb::dict d = nb::cast<nb::dict>(data);
            return nb::cast(MaterialHandle::deserialize(d));
        }),
        // convert
        nb::cpp_function([](nb::object value) -> nb::object {
            if (value.is_none()) {
                return nb::cast(MaterialHandle());
            }
            if (nb::isinstance<MaterialHandle>(value)) {
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
        // to_python: std::any(EntityHandle) → nb::object
        [](const std::any& value) -> nb::object {
            const EntityHandle& h = std::any_cast<const EntityHandle&>(value);
            return nb::cast(h);
        }
    );

    // Python handler
    tc::KindRegistry::instance().register_python(
        "entity_handle",
        // serialize
        nb::cpp_function([](nb::object obj) -> nb::object {
            if (obj.is_none()) {
                return nb::none();
            }
            try {
                EntityHandle handle = nb::cast<EntityHandle>(obj);
                if (!handle.uuid.empty()) {
                    return nb::str(handle.uuid.c_str());
                }
            } catch (const nb::cast_error&) {}
            return nb::none();
        }),
        // deserialize
        nb::cpp_function([](nb::object data) -> nb::object {
            if (nb::isinstance<nb::str>(data)) {
                return nb::cast(EntityHandle(nb::cast<std::string>(data)));
            }
            return nb::cast(EntityHandle());
        }),
        // convert
        nb::none()
    );
    // list[entity_handle] is auto-generated by InspectRegistry
}

} // namespace termin
