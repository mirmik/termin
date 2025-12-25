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
    return asset.attr("name").cast<std::string>();
}

Material* MaterialHandle::get() const {
    if (_direct != nullptr) {
        return _direct;
    }
    if (asset.is_none()) return nullptr;
    py::object res = asset.attr("resource");
    if (res.is_none()) return nullptr;
    return res.cast<Material*>();
}

Material* MaterialHandle::get_material() const {
    Material* mat = get();
    if (mat != nullptr) {
        return mat;
    }
    try {
        py::object mat_module = py::module_::import("termin.visualization.core.material");
        py::object error_mat = mat_module.attr("get_error_material")();
        return error_mat.cast<Material*>();
    } catch (const py::error_already_set&) {
        return nullptr;
    }
}

py::dict MaterialHandle::serialize() const {
    py::dict d;
    if (_direct != nullptr || asset.is_none()) {
        d["type"] = "none";
        return d;
    }
    d["type"] = "uuid";
    d["uuid"] = asset.attr("uuid");
    return d;
}

} // namespace termin
