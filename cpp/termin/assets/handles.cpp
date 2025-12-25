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
    if (_direct != nullptr) {
        if (!_direct->source_path.empty()) {
            py::dict d;
            d["type"] = "path";
            d["path"] = _direct->source_path;
            return d;
        }
        py::dict d;
        d["type"] = "direct_unsupported";
        return d;
    }
    if (asset.is_none()) {
        py::dict d;
        d["type"] = "none";
        return d;
    }
    py::dict d;
    d["uuid"] = asset.attr("uuid");
    py::object source_path = asset.attr("source_path");
    if (!source_path.is_none()) {
        d["type"] = "path";
        d["path"] = py::str(source_path.attr("as_posix")());
    } else {
        d["type"] = "named";
        d["name"] = asset.attr("name");
    }
    return d;
}

} // namespace termin
