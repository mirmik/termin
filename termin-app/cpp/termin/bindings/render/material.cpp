#include "common.hpp"

#include <tgfx/tgfx_material_handle.hpp>

#include "termin/inspect/tc_kind.hpp"

namespace termin {

void bind_material(nb::module_& m) {
    // Old MaterialPhase and Material classes removed - use TcMaterialPhase and TcMaterial.
    (void)m;
}

void bind_tc_material(nb::module_& m) {
    nb::module_ materials = nb::module_::import_("termin.materials._materials_native");
    m.attr("TcRenderState") = materials.attr("TcRenderState");
    m.attr("TcMaterialPhase") = materials.attr("TcMaterialPhase");
    m.attr("TcMaterial") = materials.attr("TcMaterial");
    m.attr("tc_material_get_all_info") = materials.attr("tc_material_get_all_info");
    m.attr("tc_material_count") = materials.attr("tc_material_count");
}

void register_material_kind_handlers() {
    nb::module_ materials = nb::module_::import_("termin.materials._materials_native");

    // C++ handler for C++ fields remains in app because inspect is app/editor infrastructure.
    tc::register_cpp_handle_kind<TcMaterial>("tc_material");

    // Register TcMaterial Python type -> "tc_material" kind mapping.
    tc::KindRegistry::instance().register_type(materials.attr("TcMaterial"), "tc_material");

    // Python handler for Python fields.
    tc::KindRegistry::instance().register_python(
        "tc_material",
        // serialize
        nb::cpp_function([](nb::object obj) -> nb::object {
            TcMaterial mat = nb::cast<TcMaterial>(obj);
            nb::dict d;
            if (!mat.is_valid()) {
                d["type"] = "none";
                return d;
            }
            d["uuid"] = mat.uuid();
            d["name"] = mat.name();
            d["type"] = "uuid";
            return d;
        }),
        // deserialize
        nb::cpp_function([](nb::object data) -> nb::object {
            if (nb::isinstance<nb::str>(data)) {
                return nb::cast(TcMaterial::from_uuid(nb::cast<std::string>(data)));
            }
            if (nb::isinstance<nb::dict>(data)) {
                nb::dict d = nb::cast<nb::dict>(data);
                if (d.contains("uuid")) {
                    std::string uuid = nb::cast<std::string>(d["uuid"]);
                    return nb::cast(TcMaterial::from_uuid(uuid));
                }
            }
            return nb::cast(TcMaterial());
        })
    );
}

} // namespace termin
