#pragma once

#include <string>
#include <nanobind/nanobind.h>
#include "../../trent/trent.h"
#include "../../core_c/include/tc_scene.h"

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

    VoxelGridHandle() : asset(nb::none()) {}

    explicit VoxelGridHandle(nb::object asset_) : asset(std::move(asset_)) {}

    // Create handle by name lookup in ResourceManager.
    static VoxelGridHandle from_name(const std::string& name);

    // Create handle from Python VoxelGridAsset.
    static VoxelGridHandle from_asset(nb::object asset) {
        return VoxelGridHandle(std::move(asset));
    }

    // Create handle by UUID lookup in ResourceManager.
    static VoxelGridHandle from_uuid(const std::string& uuid);

    // Check if handle is valid (has asset).
    bool is_valid() const {
        return !asset.is_none();
    }

    // Get asset name.
    std::string name() const {
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
        if (asset.is_none()) return 0;
        return nb::cast<int>(asset.attr("version"));
    }

    // Serialize for scene saving.
    nb::dict serialize() const {
        if (asset.is_none()) {
            nb::dict d;
            d["type"] = "none";
            return d;
        }
        nb::dict d;
        d["uuid"] = asset.attr("uuid");
        d["name"] = asset.attr("name");
        nb::object source_path = asset.attr("source_path");
        if (!source_path.is_none()) {
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
    void deserialize_from(const nos::trent& data, tc_scene* scene = nullptr);
};

} // namespace termin

#include "voxel_grid_handle_inline.hpp"
