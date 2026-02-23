#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/shared_ptr.h>
#include <nanobind/ndarray.h>

#include "handles.hpp"
#include "tgfx/graphics_backend.hpp"
#include "termin/material/tc_material_handle.hpp"
#include "termin/entity/entity.hpp"
#include "termin/inspect/tc_kind.hpp"
#include "termin/bindings/inspect/tc_inspect_python.hpp"
#include "../skeleton/tc_skeleton_handle.hpp"
#include <tcbase/tc_log.hpp>

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
            tc_value val = mat.serialize_to_value();
            nb::object result = tc::tc_value_to_nb(&val);
            tc_value_free(&val);
            return result;
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
        })
    );

    // ===== tc_skeleton kind =====
    // C++ handler
    tc::KindRegistryCpp::instance().register_kind("tc_skeleton",
        // serialize: std::any(TcSkeleton) → tc_value
        [](const std::any& value) -> tc_value {
            const TcSkeleton& s = std::any_cast<const TcSkeleton&>(value);
            tc_value result = tc_value_dict_new();
            if (s.is_valid()) {
                tc_value_dict_set(&result, "uuid", tc_value_string(s.uuid()));
                tc_value_dict_set(&result, "name", tc_value_string(s.name()));
            }
            return result;
        },
        // deserialize: tc_value, scene → std::any(TcSkeleton)
        [](const tc_value* v, tc_scene_handle) -> std::any {
            if (!v || v->type != TC_VALUE_DICT) return TcSkeleton();
            tc_value* uuid_val = tc_value_dict_get(const_cast<tc_value*>(v), "uuid");
            if (!uuid_val || uuid_val->type != TC_VALUE_STRING || !uuid_val->data.s) {
                return TcSkeleton();
            }
            std::string uuid = uuid_val->data.s;
            TcSkeleton skel = TcSkeleton::from_uuid(uuid);
            if (!skel.is_valid()) {
                tc_value* name_val = tc_value_dict_get(const_cast<tc_value*>(v), "name");
                std::string name = (name_val && name_val->type == TC_VALUE_STRING && name_val->data.s)
                    ? name_val->data.s : "";
                tc::Log::warn("tc_skeleton deserialize: skeleton not found, uuid=%s name=%s", uuid.c_str(), name.c_str());
            } else {
                skel.ensure_loaded();
            }
            return skel;
        }
    );

    // Python handler for tc_skeleton kind
    tc::KindRegistry::instance().register_python(
        "tc_skeleton",
        nb::cpp_function([](nb::object obj) -> nb::object {
            TcSkeleton skel = nb::cast<TcSkeleton>(obj);
            nb::dict d;
            if (skel.is_valid()) {
                d["uuid"] = nb::str(skel.uuid());
                d["name"] = nb::str(skel.name());
            }
            return d;
        }),
        nb::cpp_function([](nb::object data) -> nb::object {
            if (!nb::isinstance<nb::dict>(data)) {
                return nb::cast(TcSkeleton());
            }
            nb::dict d = nb::cast<nb::dict>(data);
            if (!d.contains("uuid")) {
                return nb::cast(TcSkeleton());
            }
            std::string uuid = nb::cast<std::string>(d["uuid"]);
            return nb::cast(TcSkeleton::from_uuid(uuid));
        })
    );

    // ===== entity kind =====
    tc::register_cpp_handle_kind<Entity>("entity");
}

} // namespace termin
