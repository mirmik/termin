#pragma once

#include <string>
#include <pybind11/pybind11.h>
#include "../../trent/trent.h"

namespace py = pybind11;

namespace termin {

/**
 * VoxelGridHandle - smart reference to voxel grid asset.
 *
 * Wraps VoxelGridAsset py::object, provides:
 * - Access to VoxelGrid
 * - Serialization/deserialization with UUID
 */
class VoxelGridHandle {
public:
    // Python asset object (VoxelGridAsset or None)
    py::object asset;

    VoxelGridHandle() : asset(py::none()) {}

    explicit VoxelGridHandle(py::object asset_) : asset(std::move(asset_)) {}

    /**
     * Create handle by name lookup in ResourceManager.
     */
    static VoxelGridHandle from_name(const std::string& name);

    /**
     * Create handle from Python VoxelGridAsset.
     */
    static VoxelGridHandle from_asset(py::object asset) {
        return VoxelGridHandle(std::move(asset));
    }

    /**
     * Create handle by UUID lookup in ResourceManager.
     */
    static VoxelGridHandle from_uuid(const std::string& uuid);

    /**
     * Check if handle is valid (has asset).
     */
    bool is_valid() const {
        return !asset.is_none();
    }

    /**
     * Get asset name.
     */
    std::string name() const {
        if (asset.is_none()) return "";
        return asset.attr("name").cast<std::string>();
    }

    /**
     * Get VoxelGrid object (returns py::object).
     * Returns None if asset is empty or resource is None.
     */
    py::object get() const;

    /**
     * Convenience alias.
     */
    py::object grid() const { return get(); }

    /**
     * Serialize for scene saving.
     */
    py::dict serialize() const {
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

    /**
     * Deserialize from scene data.
     */
    static VoxelGridHandle deserialize(const py::dict& data);

    /**
     * Deserialize inplace from scene data.
     */
    void deserialize_from(const nos::trent& data);
};

} // namespace termin

#include "voxel_grid_handle_inline.hpp"
