// Non-inline implementations for MaterialHandle methods that need Material definition.
// Other handle methods are inline in handles_inline.hpp.

#include "handles.hpp"
#include "termin/render/material.hpp"

namespace termin {

std::string MaterialHandle::name() const {
    if (_direct != nullptr) {
        return _direct->name;
    }
    if (asset.is_none()) return "";
    return nb::cast<std::string>(asset.attr("name"));
}

Material* MaterialHandle::get() const {
    if (_direct != nullptr) {
        return _direct;
    }
    if (asset.is_none()) return nullptr;
    nb::object res = asset.attr("resource");
    if (res.is_none()) return nullptr;
    return nb::cast<Material*>(res);
}

Material* MaterialHandle::get_material() const {
    Material* mat = get();
    if (mat != nullptr) {
        return mat;
    }
    try {
        nb::object mat_module = nb::module_::import_("termin.visualization.core.material");
        nb::object error_mat = mat_module.attr("get_error_material")();
        return nb::cast<Material*>(error_mat);
    } catch (const nb::python_error&) {
        return nullptr;
    }
}

nb::dict MaterialHandle::serialize() const {
    nb::dict d;
    if (_direct != nullptr || asset.is_none()) {
        d["type"] = "none";
        return d;
    }
    d["type"] = "uuid";
    d["uuid"] = asset.attr("uuid");
    return d;
}

} // namespace termin
