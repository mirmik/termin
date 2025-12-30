#pragma once

#include "termin/voxels/voxel_grid.hpp"

namespace termin {

inline VoxelGridHandle VoxelGridHandle::from_name(const std::string& name) {
    try {
        nb::object rm_module = nb::module_::import_("termin.assets.resources");
        nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
        nb::object asset = rm.attr("get_voxel_grid_asset")(name);
        if (asset.is_none()) {
            return VoxelGridHandle();
        }
        return VoxelGridHandle(asset);
    } catch (const nb::python_error&) {
        return VoxelGridHandle();
    }
}

inline VoxelGridHandle VoxelGridHandle::from_uuid(const std::string& uuid) {
    try {
        nb::object rm_module = nb::module_::import_("termin.assets.resources");
        nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
        nb::object asset = rm.attr("get_voxel_grid_asset_by_uuid")(uuid);
        if (asset.is_none()) {
            return VoxelGridHandle();
        }
        return VoxelGridHandle(asset);
    } catch (const nb::python_error&) {
        return VoxelGridHandle();
    }
}

inline nb::object VoxelGridHandle::get() const {
    if (asset.is_none()) return nb::none();
    nb::object res = asset.attr("resource");
    return res;  // Returns the VoxelGrid object (or None)
}

inline VoxelGridHandle VoxelGridHandle::deserialize(const nb::dict& data) {
    // Try UUID first
    if (data.contains("uuid")) {
        try {
            std::string uuid = nb::cast<std::string>(data["uuid"]);
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object asset = rm.attr("get_voxel_grid_asset_by_uuid")(uuid);
            if (!asset.is_none()) {
                return VoxelGridHandle(asset);
            }
        } catch (const nb::python_error&) {}
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
        } catch (const nb::python_error&) {
            return VoxelGridHandle();
        }
    }

    return VoxelGridHandle();
}

inline void VoxelGridHandle::deserialize_from(const nos::trent& data) {
    if (!data.is_dict()) {
        asset = nb::none();
        return;
    }

    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].as_string();
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object found = rm.attr("get_voxel_grid_asset_by_uuid")(uuid);
            if (!found.is_none()) {
                asset = found;
                return;
            }
        } catch (...) {}
    }

    std::string type = data.contains("type") ? data["type"].as_string() : "none";

    if (type == "named") {
        std::string name = data["name"].as_string();
        asset = from_name(name).asset;
    } else if (type == "path") {
        std::string path = data["path"].as_string();
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

} // namespace termin
