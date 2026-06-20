#pragma once

#include <string>
#include <nanobind/nanobind.h>
#include "inspect/tc_inspect.h"
#include "termin/voxels/tc_voxel_grid_handle.hpp"

namespace nb = nanobind;

namespace termin {

// VoxelGridHandle - smart reference to voxel grid asset.
//
// Wraps VoxelGridAsset nb::object, provides:
// - Access to VoxelGrid
// - Serialization/deserialization with UUID
class VoxelGridHandle {
public:
    // Python asset object (VoxelGridAsset or None)
    nb::object asset;
    voxels::TcVoxelGrid native;

    VoxelGridHandle() : asset(nb::none()), native() {}

    explicit VoxelGridHandle(nb::object asset_) : asset(std::move(asset_)), native() {}

    explicit VoxelGridHandle(voxels::TcVoxelGrid native_)
        : asset(nb::none()), native(std::move(native_)) {}

    VoxelGridHandle(voxels::TcVoxelGrid native_, nb::object asset_)
        : asset(std::move(asset_)), native(std::move(native_)) {}

    // Create handle by name lookup in ResourceManager.
    static VoxelGridHandle from_name(const std::string& name);

    // Create handle from Python VoxelGridAsset.
    static VoxelGridHandle from_asset(nb::object asset);

    // Create handle by UUID lookup in ResourceManager.
    static VoxelGridHandle from_uuid(const std::string& uuid);

    // Check if handle is valid (has asset).
    bool is_valid() const {
        return native.is_valid() || !asset.is_none();
    }

    // Get asset name.
    std::string name() const {
        if (native.is_valid() && native.name()[0] != '\0') return native.name();
        if (asset.is_none()) return "";
        return nb::cast<std::string>(asset.attr("name"));
    }

    // Get VoxelGrid object (returns nb::object).
    // Returns None if asset is empty or resource is None.
    nb::object get() const;

    // Convenience alias.
    nb::object grid() const { return get(); }

    // Get version from asset (for change detection).
    int version() const {
        if (native.is_valid()) return static_cast<int>(native.version());
        if (asset.is_none()) return 0;
        return nb::cast<int>(asset.attr("version"));
    }

    // Serialize for kind registry (returns tc_value)
    tc_value serialize_to_value() const {
        tc_value d = tc_value_dict_new();
        if (!native.is_valid() && asset.is_none()) {
            tc_value_dict_set(&d, "type", tc_value_string("none"));
            return d;
        }
        std::string uuid_str = native.is_valid() ? native.uuid() : nb::cast<std::string>(asset.attr("uuid"));
        std::string name_str = name();
        tc_value_dict_set(&d, "uuid", tc_value_string(uuid_str.c_str()));
        tc_value_dict_set(&d, "name", tc_value_string(name_str.c_str()));
        std::string native_source_path = native.is_valid() ? native.source_path() : "";
        if (!native_source_path.empty()) {
            tc_value_dict_set(&d, "type", tc_value_string("path"));
            tc_value_dict_set(&d, "path", tc_value_string(native_source_path.c_str()));
        } else if (!asset.is_none() && !asset.attr("source_path").is_none()) {
            nb::object source_path = asset.attr("source_path");
            tc_value_dict_set(&d, "type", tc_value_string("path"));
            std::string path_str = nb::cast<std::string>(nb::str(source_path.attr("as_posix")()));
            tc_value_dict_set(&d, "path", tc_value_string(path_str.c_str()));
        } else {
            tc_value_dict_set(&d, "type", tc_value_string("named"));
        }
        return d;
    }

    // Serialize for scene saving (returns nanobind dict) - for Python bindings
    nb::dict serialize() const {
        if (!native.is_valid() && asset.is_none()) {
            nb::dict d;
            d["type"] = "none";
            return d;
        }
        nb::dict d;
        if (native.is_valid()) {
            d["uuid"] = std::string(native.uuid());
        } else {
            d["uuid"] = asset.attr("uuid");
        }
        d["name"] = name();
        std::string native_source_path = native.is_valid() ? native.source_path() : "";
        if (!native_source_path.empty()) {
            d["type"] = "path";
            d["path"] = native_source_path;
        } else if (!asset.is_none() && !asset.attr("source_path").is_none()) {
            nb::object source_path = asset.attr("source_path");
            d["type"] = "path";
            d["path"] = nb::str(source_path.attr("as_posix")());
        } else {
            d["type"] = "named";
        }
        return d;
    }

    // Deserialize from scene data.
    static VoxelGridHandle deserialize(const nb::dict& data);

    // Deserialize inplace from scene data.
    void deserialize_from(const tc_value* data, void* context = nullptr);
};

} // namespace termin

#include "voxel_grid_handle_inline.hpp"
