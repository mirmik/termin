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

inline voxels::VoxelGrid* VoxelGridHandle::get() const {
    if (asset.is_none()) return nullptr;
    py::object res = asset.attr("resource");
    if (res.is_none()) return nullptr;
    return res.cast<voxels::VoxelGrid*>();
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

} // namespace termin
