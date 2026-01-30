#pragma once

// Inline implementations for handle methods.
// Include this at the end of handles.hpp.
// These implementations use nb::module_::import, so they can be
// compiled in any module that includes handles.hpp.
//
// Note: MaterialHandle methods that access Material members are NOT inline
// because they would create circular dependencies. They are in handles.cpp.

#include "tc_log.hpp"

namespace termin {

// Helper to get string from tc_value dict by key
inline std::string tc_value_dict_get_string(const tc_value* dict, const char* key, const char* default_val = "") {
    if (!dict || dict->type != TC_VALUE_DICT) return default_val;
    tc_value* v = tc_value_dict_get(const_cast<tc_value*>(dict), key);
    if (!v || v->type != TC_VALUE_STRING || !v->data.s) return default_val;
    return v->data.s;
}

// ========== TextureHandle inline implementations ==========

inline TextureHandle TextureHandle::from_name(const std::string& name) {
    try {
        nb::object rm_module = nb::module_::import_("termin.assets.resources");
        nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
        nb::object asset = rm.attr("get_texture_asset")(name);
        if (asset.is_none()) {
            return TextureHandle();
        }
        return TextureHandle(asset);
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "TextureHandle::from_name('%s')", name.c_str());
        return TextureHandle();
    }
}

inline TextureHandle TextureHandle::from_file(
    const std::string& path,
    const std::string& name
) {
    try {
        nb::object texture_asset_module = nb::module_::import_("termin.visualization.render.texture_asset");
        nb::object TextureAsset = texture_asset_module.attr("TextureAsset");

        nb::object asset;
        if (name.empty()) {
            asset = TextureAsset.attr("from_file")(path);
        } else {
            asset = TextureAsset.attr("from_file")(path, nb::arg("name") = name);
        }
        return TextureHandle(asset);
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "TextureHandle::from_file('%s')", path.c_str());
        return TextureHandle();
    }
}

inline TextureHandle TextureHandle::from_texture_data(
    nb::object texture_data,
    const std::string& name
) {
    try {
        nb::object texture_asset_module = nb::module_::import_("termin.visualization.render.texture_asset");
        nb::object TextureAsset = texture_asset_module.attr("TextureAsset");

        nb::object asset = TextureAsset(
            nb::arg("texture_data") = texture_data,
            nb::arg("name") = name
        );
        return TextureHandle(asset);
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "TextureHandle::from_texture_data('%s')", name.c_str());
        return TextureHandle();
    }
}

inline TextureHandle TextureHandle::deserialize(const nb::dict& data) {
    if (data.contains("uuid")) {
        try {
            std::string uuid = nb::cast<std::string>(data["uuid"]);
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object asset = rm.attr("get_texture_asset_by_uuid")(uuid);
            if (!asset.is_none()) {
                return TextureHandle(asset);
            }
        } catch (const nb::python_error& e) {
            tc::Log::warn(e, "TextureHandle::deserialize uuid lookup");
        }
    }

    std::string type = data.contains("type") ? nb::cast<std::string>(data["type"]) : "none";

    if (type == "named") {
        std::string name = nb::cast<std::string>(data["name"]);
        return from_name(name);
    } else if (type == "path") {
        try {
            std::string path = nb::cast<std::string>(data["path"]);
            size_t last_slash = path.find_last_of("/\\");
            std::string filename = (last_slash != std::string::npos)
                ? path.substr(last_slash + 1) : path;
            size_t last_dot = filename.find_last_of('.');
            std::string name = (last_dot != std::string::npos)
                ? filename.substr(0, last_dot) : filename;
            return from_name(name);
        } catch (const nb::python_error& e) {
            tc::Log::warn(e, "TextureHandle::deserialize path lookup");
            return TextureHandle();
        }
    }

    return TextureHandle();
}

inline void TextureHandle::deserialize_from(const tc_value* data, tc_scene_handle) {
    _direct = TcTexture();

    if (!data || data->type != TC_VALUE_DICT) {
        asset = nb::none();
        return;
    }

    std::string uuid = tc_value_dict_get_string(data, "uuid");
    if (!uuid.empty()) {
        try {
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object found = rm.attr("get_texture_asset_by_uuid")(uuid);
            if (!found.is_none()) {
                asset = found;
                return;
            }
        } catch (const std::exception& e) {
            tc::Log::warn(e, "TextureHandle::deserialize_from uuid lookup");
        }
    }

    std::string type = tc_value_dict_get_string(data, "type", "none");

    if (type == "named") {
        std::string name = tc_value_dict_get_string(data, "name");
        asset = from_name(name).asset;
    } else if (type == "path") {
        std::string path = tc_value_dict_get_string(data, "path");
        size_t last_slash = path.find_last_of("/\\");
        std::string filename = (last_slash != std::string::npos)
            ? path.substr(last_slash + 1) : path;
        size_t last_dot = filename.find_last_of('.');
        std::string name = (last_dot != std::string::npos)
            ? filename.substr(0, last_dot) : filename;
        asset = from_name(name).asset;
    } else {
        asset = nb::none();
    }
}

// ========== get_white_texture_handle ==========

inline TextureHandle get_white_texture_handle() {
    // Use Python singleton instead of C++ static to ensure consistency across modules
    try {
        nb::object texture_handle_module = nb::module_::import_("termin.visualization.core.texture_handle");
        nb::object handle = texture_handle_module.attr("get_white_texture_handle")();
        return nb::cast<TextureHandle>(handle);
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "get_white_texture_handle");
        return TextureHandle();
    }
}

} // namespace termin
