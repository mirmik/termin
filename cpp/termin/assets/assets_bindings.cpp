#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/shared_ptr.h>
#include <nanobind/ndarray.h>

#include "handles.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/material/tc_material_handle.hpp"
#include "termin/entity/entity.hpp"
#include "../../../core_c/include/tc_kind.hpp"
#include "tc_log.hpp"

namespace nb = nanobind;

namespace termin {

// Forward declaration
void register_kind_handlers();

void bind_assets(nb::module_& m) {
    // Note: TcTexture is now in _texture_native module

    // ========== TextureHandle ==========
    nb::class_<TextureHandle>(m, "TextureHandle")
        .def(nb::init<>())
        .def(nb::init<nb::object>(), nb::arg("asset"))
        .def_static("from_name", &TextureHandle::from_name, nb::arg("name"))
        .def_static("from_asset", &TextureHandle::from_asset, nb::arg("asset"))
        .def_static("from_direct", &TextureHandle::from_direct, nb::arg("texture"))
        .def_static("from_file", &TextureHandle::from_file,
            nb::arg("path"), nb::arg("name") = "")
        .def_static("from_texture_data", &TextureHandle::from_texture_data,
            nb::arg("texture_data"), nb::arg("name") = "texture")
        .def_static("deserialize", &TextureHandle::deserialize, nb::arg("data"))
        .def_rw("_direct", &TextureHandle::_direct)
        .def_rw("asset", &TextureHandle::asset)
        .def_prop_ro("is_valid", &TextureHandle::is_valid)
        .def_prop_ro("is_direct", &TextureHandle::is_direct)
        .def_prop_ro("name", &TextureHandle::name)
        .def_prop_ro("version", &TextureHandle::version)
        .def_prop_ro("source_path", &TextureHandle::source_path)
        .def("get", &TextureHandle::get)
        .def("get_asset", [](const TextureHandle& self) { return self.asset; })
        .def("serialize", &TextureHandle::serialize);

    // Note: TcMaterial is bound in _render_native module

    // Note: TcSkeleton is now in _skeleton_native module

    // ========== Free functions ==========
    m.def("get_white_texture_handle", &get_white_texture_handle,
        "Get a white 1x1 texture handle (singleton).");

    // Register kind handlers for serialization
    register_kind_handlers();
}

void register_kind_handlers() {
    // Note: mesh_handle kind is registered in _mesh_native module

    // ===== tc_material kind =====
    // C++ handler for C++ fields
    tc::register_cpp_handle_kind<TcMaterial>("tc_material");

    // Python handler for Python fields
    tc::KindRegistry::instance().register_python(
        "tc_material",
        // serialize
        nb::cpp_function([](nb::object obj) -> nb::object {
            TcMaterial mat = nb::cast<TcMaterial>(obj);
            return mat.serialize();
        }),
        // deserialize
        nb::cpp_function([](nb::object data) -> nb::object {
            if (data.is_none()) {
                return nb::cast(TcMaterial());
            }

            nb::dict d = nb::cast<nb::dict>(data);
            // Try uuid first
            if (d.contains("uuid")) {
                std::string uuid = nb::cast<std::string>(d["uuid"]);
                TcMaterial mat = TcMaterial::from_uuid(uuid);
                if (mat.is_valid()) {
                    return nb::cast(mat);
                }
            }
            // Try name
            if (d.contains("name")) {
                std::string name = nb::cast<std::string>(d["name"]);
                TcMaterial mat = TcMaterial::from_name(name);
                if (mat.is_valid()) {
                    return nb::cast(mat);
                }
            }
            return nb::cast(TcMaterial());
        }),
        // convert
        nb::cpp_function([](nb::object value) -> nb::object {
            if (value.is_none()) {
                return nb::cast(TcMaterial());
            }
            if (nb::isinstance<TcMaterial>(value)) {
                return value;
            }
            // Try string (material name)
            if (nb::isinstance<nb::str>(value)) {
                std::string name = nb::cast<std::string>(value);
                return nb::cast(TcMaterial::from_name(name));
            }
            return nb::cast(TcMaterial());
        })
    );

    // Note: tc_skeleton kind is registered in _skeleton_native module

    // ===== entity kind =====
    tc::register_cpp_handle_kind<Entity>("entity");
}

} // namespace termin
