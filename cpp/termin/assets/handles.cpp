// Non-inline implementations for MaterialHandle methods that need Material definition.
// Other handle methods are inline in handles_inline.hpp.

#include "handles.hpp"
#include "termin/render/material.hpp"
#include "tc_log.hpp"

namespace termin {

std::string MaterialHandle::name() const {
    if (_direct != nullptr) {
        return _direct->name;
    }
    if (asset.is_none()) return "";

    // Check if asset is a Material directly (has .name as string)
    // or if it's an asset wrapper
    try {
        Material* mat = nb::cast<Material*>(asset);
        return mat->name;
    } catch (...) {
        try {
            return nb::cast<std::string>(asset.attr("name"));
        } catch (...) {
            return "";
        }
    }
}

Material* MaterialHandle::get() const {
    if (_direct != nullptr) {
        return _direct;
    }
    if (asset.is_none()) return nullptr;

    // Check if asset is a Material directly (e.g. UnknownMaterial)
    // or if it's an asset wrapper with .resource attribute
    try {
        // Try to cast directly to Material* first
        return nb::cast<Material*>(asset);
    } catch (...) {
        // Not a Material, try to get .resource
        try {
            nb::object res = asset.attr("resource");
            if (res.is_none()) return nullptr;
            return nb::cast<Material*>(res);
        } catch (...) {
            return nullptr;
        }
    }
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
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "MaterialHandle::get_material fallback");
        return nullptr;
    }
}

nb::dict MaterialHandle::serialize() const {
    nb::dict d;
    if (_direct != nullptr || asset.is_none()) {
        d["type"] = "none";
        return d;
    }

    // Check if asset is a Material directly (e.g. UnknownMaterial)
    // If so, call its serialize() method which preserves original data
    try {
        Material* mat = nb::cast<Material*>(asset);
        // It's a Material - call its serialize method
        nb::object py_mat = asset;
        if (nb::hasattr(py_mat, "serialize")) {
            return nb::cast<nb::dict>(py_mat.attr("serialize")());
        }
        d["type"] = "none";
        return d;
    } catch (...) {
        // Not a Material directly, it's an asset wrapper with uuid
        try {
            d["type"] = "uuid";
            d["uuid"] = asset.attr("uuid");
            d["name"] = asset.attr("name");
            return d;
        } catch (...) {
            d["type"] = "none";
            return d;
        }
    }
}

} // namespace termin
