#pragma once

#include "termin/voxels/voxel_grid.hpp"
#include <tcbase/tc_log.hpp>

namespace termin {

inline std::string voxel_handle_tc_value_dict_get_string(
    const tc_value* dict,
    const char* key,
    const char* default_val = ""
) {
    if (!dict || dict->type != TC_VALUE_DICT) return default_val;
    tc_value* v = tc_value_dict_get(const_cast<tc_value*>(dict), key);
    if (!v || v->type != TC_VALUE_STRING || !v->data.s) return default_val;
    return v->data.s;
}

inline VoxelGridHandle VoxelGridHandle::from_name(const std::string& name) {
    voxels::TcVoxelGrid native = voxels::TcVoxelGrid::from_name(name);
    try {
        nb::object rm_module = nb::module_::import_("termin.assets.resources");
        nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
        nb::object asset = rm.attr("get_voxel_grid_asset")(name);
        if (asset.is_none()) {
            return native.is_valid() ? VoxelGridHandle(std::move(native)) : VoxelGridHandle();
        }
        if (!native.is_valid()) {
            return VoxelGridHandle::from_asset(asset);
        }
        return VoxelGridHandle(std::move(native), asset);
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "VoxelGridHandle::from_name('%s')", name.c_str());
        return native.is_valid() ? VoxelGridHandle(std::move(native)) : VoxelGridHandle();
    }
}

inline VoxelGridHandle VoxelGridHandle::from_uuid(const std::string& uuid) {
    voxels::TcVoxelGrid native = voxels::TcVoxelGrid::from_uuid(uuid);
    try {
        nb::object rm_module = nb::module_::import_("termin.assets.resources");
        nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
        nb::object asset = rm.attr("get_voxel_grid_asset_by_uuid")(uuid);
        if (asset.is_none()) {
            return native.is_valid() ? VoxelGridHandle(std::move(native)) : VoxelGridHandle();
        }
        if (!native.is_valid()) {
            return VoxelGridHandle::from_asset(asset);
        }
        return VoxelGridHandle(std::move(native), asset);
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "VoxelGridHandle::from_uuid('%s')", uuid.c_str());
        return native.is_valid() ? VoxelGridHandle(std::move(native)) : VoxelGridHandle();
    }
}

inline VoxelGridHandle VoxelGridHandle::from_asset(nb::object asset) {
    if (asset.is_none()) {
        return VoxelGridHandle();
    }
    try {
        std::string uuid = nb::cast<std::string>(asset.attr("uuid"));
        std::string name = nb::cast<std::string>(asset.attr("name"));
        voxels::TcVoxelGrid native = voxels::TcVoxelGrid::declare(uuid, name);
        if (tc_voxel_grid* grid = native.get()) {
            nb::object source_path = asset.attr("source_path");
            if (!source_path.is_none()) {
                std::string path = nb::cast<std::string>(nb::str(source_path.attr("as_posix")()));
                tc_voxel_grid_set_metadata(grid, name.c_str(), path.c_str());
            } else {
                tc_voxel_grid_set_metadata(grid, name.c_str(), nullptr);
            }
        }
        return VoxelGridHandle(std::move(native), std::move(asset));
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "VoxelGridHandle::from_asset");
        return VoxelGridHandle(std::move(asset));
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
            VoxelGridHandle handle = from_uuid(uuid);
            if (handle.is_valid()) return handle;
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

inline void VoxelGridHandle::deserialize_from(const tc_value* data, void*) {
    if (!data || data->type != TC_VALUE_DICT) {
        asset = nb::none();
        return;
    }

    std::string uuid = voxel_handle_tc_value_dict_get_string(data, "uuid");
    if (!uuid.empty()) {
        VoxelGridHandle found = from_uuid(uuid);
        if (found.is_valid()) {
            native = std::move(found.native);
            asset = found.asset;
            return;
        }
    }

    std::string type = voxel_handle_tc_value_dict_get_string(data, "type", "none");

    if (type == "named") {
        std::string name = voxel_handle_tc_value_dict_get_string(data, "name");
        VoxelGridHandle found = from_name(name);
        native = std::move(found.native);
        asset = found.asset;
    } else if (type == "path") {
        std::string path = voxel_handle_tc_value_dict_get_string(data, "path");
        size_t last_slash = path.find_last_of("/\\");
        std::string filename = (last_slash != std::string::npos)
            ? path.substr(last_slash + 1) : path;
        size_t last_dot = filename.find_last_of('.');
        std::string name = (last_dot != std::string::npos)
            ? filename.substr(0, last_dot) : filename;
        VoxelGridHandle found = from_name(name);
        native = std::move(found.native);
        asset = found.asset;
    } else {
        native = voxels::TcVoxelGrid();
        asset = nb::none();
    }
}

} // namespace termin
