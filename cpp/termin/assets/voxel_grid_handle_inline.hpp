#pragma once

#include "termin/voxels/voxel_grid.hpp"
#include "tc_log.hpp"

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
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "VoxelGridHandle::from_name('%s')", name.c_str());
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
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "VoxelGridHandle::from_uuid('%s')", uuid.c_str());
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
        } catch (const nb::python_error& e) {
            tc::Log::warn(e, "VoxelGridHandle::deserialize uuid lookup");
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
            tc::Log::warn(e, "VoxelGridHandle::deserialize path lookup");
            return VoxelGridHandle();
        }
    }

    return VoxelGridHandle();
}

inline void VoxelGridHandle::deserialize_from(const tc_value* data, tc_scene_handle) {
    if (!data || data->type != TC_VALUE_DICT) {
        asset = nb::none();
        return;
    }

    std::string uuid = tc_value_dict_get_string(data, "uuid");
    if (!uuid.empty()) {
        try {
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object found = rm.attr("get_voxel_grid_asset_by_uuid")(uuid);
            if (!found.is_none()) {
                asset = found;
                return;
            }
        } catch (const std::exception& e) {
            tc::Log::warn(e, "VoxelGridHandle::deserialize_from uuid lookup");
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

} // namespace termin
