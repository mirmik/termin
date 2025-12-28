#pragma once

#include "termin/voxels/voxel_grid.hpp"

namespace termin {

inline VoxelGridHandle VoxelGridHandle::from_name(const std::string& name) {
    try {
        py::object rm_module = py::module_::import("termin.assets.resources");
        py::object rm = rm_module.attr("ResourceManager").attr("instance")();
        py::object asset = rm.attr("get_voxel_grid_asset")(name);
        if (asset.is_none()) {
            return VoxelGridHandle();
        }
        return VoxelGridHandle(asset);
    } catch (const py::error_already_set&) {
        return VoxelGridHandle();
    }
}

inline VoxelGridHandle VoxelGridHandle::from_uuid(const std::string& uuid) {
    try {
        py::object rm_module = py::module_::import("termin.assets.resources");
        py::object rm = rm_module.attr("ResourceManager").attr("instance")();
        py::object asset = rm.attr("get_voxel_grid_asset_by_uuid")(uuid);
        if (asset.is_none()) {
            return VoxelGridHandle();
        }
        return VoxelGridHandle(asset);
    } catch (const py::error_already_set&) {
        return VoxelGridHandle();
    }
}

inline py::object VoxelGridHandle::get() const {
    if (asset.is_none()) return py::none();
    py::object res = asset.attr("resource");
    return res;  // Returns the VoxelGrid object (or None)
}

inline VoxelGridHandle VoxelGridHandle::deserialize(const py::dict& data) {
    // Try UUID first
    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].cast<std::string>();
            py::object rm_module = py::module_::import("termin.assets.resources");
            py::object rm = rm_module.attr("ResourceManager").attr("instance")();
            py::object asset = rm.attr("get_voxel_grid_asset_by_uuid")(uuid);
            if (!asset.is_none()) {
                return VoxelGridHandle(asset);
            }
        } catch (const py::error_already_set&) {}
    }

    std::string type = data.contains("type") ? data["type"].cast<std::string>() : "none";

    if (type == "named") {
        std::string name = data["name"].cast<std::string>();
        return from_name(name);
    } else if (type == "path") {
        try {
            std::string path = data["path"].cast<std::string>();
            size_t last_slash = path.find_last_of("/\\");
            std::string filename = (last_slash != std::string::npos)
                ? path.substr(last_slash + 1) : path;
            size_t last_dot = filename.find_last_of('.');
            std::string name = (last_dot != std::string::npos)
                ? filename.substr(0, last_dot) : filename;
            return from_name(name);
        } catch (const py::error_already_set&) {
            return VoxelGridHandle();
        }
    }

    return VoxelGridHandle();
}

inline void VoxelGridHandle::deserialize_from(const nos::trent& data) {
    if (!data.is_dict()) {
        asset = py::none();
        return;
    }

    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].as_string();
            py::object rm_module = py::module_::import("termin.assets.resources");
            py::object rm = rm_module.attr("ResourceManager").attr("instance")();
            py::object found = rm.attr("get_voxel_grid_asset_by_uuid")(uuid);
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
        asset = py::none();
    }
}

} // namespace termin
