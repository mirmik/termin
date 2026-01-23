#pragma once

#include <string>
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>

#include "../../core_c/include/tc_scene.h"
#include "../../core_c/include/tc_inspect.h"
#include "termin/render/handles.hpp"
#include "termin/mesh/tc_mesh_handle.hpp"
#include "termin/texture/tc_texture_handle.hpp"

namespace nb = nanobind;

namespace termin {

/**
 * TextureHandle - smart reference to texture asset.
 *
 * Wraps TextureAsset nb::object, provides access to TcTexture and GPU handle.
 */
class TextureHandle {
public:
    // Direct texture (optional, for non-asset textures)
    TcTexture _direct;

    // Python asset object (TextureAsset or None)
    nb::object asset;

    TextureHandle() : asset(nb::none()) {}

    explicit TextureHandle(nb::object asset_) : _direct(), asset(std::move(asset_)) {}

    explicit TextureHandle(TcTexture direct) : _direct(std::move(direct)), asset(nb::none()) {}

    // Create handle from direct TcTexture.
    static TextureHandle from_direct(TcTexture texture) {
        return TextureHandle(std::move(texture));
    }

    /**
     * Create handle by name lookup in ResourceManager.
     */
    static TextureHandle from_name(const std::string& name);

    /**
     * Create handle from Python TextureAsset.
     */
    static TextureHandle from_asset(nb::object asset) {
        return TextureHandle(std::move(asset));
    }

    /**
     * Create handle from image file path.
     */
    static TextureHandle from_file(
        const std::string& path,
        const std::string& name = ""
    );

    /**
     * Create handle from TcTexture.
     */
    static TextureHandle from_texture_data(
        nb::object texture_data,
        const std::string& name = "texture"
    );

    // Check if handle is valid (has direct texture or asset).
    bool is_valid() const {
        return _direct.is_valid() || !asset.is_none();
    }

    // Check if this is a direct texture (not from asset).
    bool is_direct() const {
        return _direct.is_valid();
    }

    // Get asset name (empty if direct).
    std::string name() const {
        if (_direct.is_valid()) return _direct.name();
        if (asset.is_none()) return "";
        return nb::cast<std::string>(asset.attr("name"));
    }

    /**
     * Get version for change tracking.
     */
    int version() const {
        if (_direct.is_valid()) return _direct.version();
        if (asset.is_none()) return 0;
        return nb::cast<int>(asset.attr("version"));
    }

    /**
     * Get TcTexture.
     * Returns invalid TcTexture if asset is empty or resource is None.
     */
    TcTexture get() const {
        if (_direct.is_valid()) {
            return _direct;
        }
        if (asset.is_none()) return TcTexture();
        nb::object res = asset.attr("resource");
        if (res.is_none()) return TcTexture();
        return nb::cast<TcTexture>(res);
    }


    /**
     * Get source path.
     */
    std::string source_path() const {
        if (_direct.is_valid()) return _direct.source_path();
        if (asset.is_none()) return "";
        nb::object sp = asset.attr("source_path");
        if (sp.is_none()) return "";
        return nb::cast<std::string>(nb::str(sp.attr("as_posix")()));
    }

    /**
     * Serialize for scene saving.
     * Always includes UUID for reliable deserialization.
     */
    nb::dict serialize() const {
        if (asset.is_none()) {
            nb::dict d;
            d["type"] = "none";
            return d;
        }
        nb::dict d;
        // Always include UUID for reliable lookup
        d["uuid"] = asset.attr("uuid");
        // Always include name for inspector display
        d["name"] = asset.attr("name");
        // Also include path for debugging and fallback
        nb::object source_path = asset.attr("source_path");
        if (!source_path.is_none()) {
            d["type"] = "path";
            d["path"] = nb::str(source_path.attr("as_posix")());
        } else {
            d["type"] = "named";
        }
        return d;
    }

    /**
     * Deserialize from scene data.
     */
    static TextureHandle deserialize(const nb::dict& data);

    /**
     * Deserialize inplace from scene data.
     */
    void deserialize_from(const tc_value* data, tc_scene* scene = nullptr);
};

/**
 * Get a white 1x1 texture handle (singleton).
 */
TextureHandle get_white_texture_handle();

} // namespace termin

// Include inline implementations
#include "handles_inline.hpp"

// Additional handle types in separate files
#include "voxel_grid_handle.hpp"
