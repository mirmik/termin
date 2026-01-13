#pragma once

#include <string>
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>

#include "../../trent/trent.h"
#include "../../core_c/include/tc_scene.h"
#include "termin/render/handles.hpp"
#include "termin/render/mesh_gpu.hpp"
#include "termin/mesh/tc_mesh_handle.hpp"
#include "termin/texture/tc_texture_handle.hpp"

namespace nb = nanobind;

namespace termin {

// Forward declarations
class Material;

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
    void deserialize_from(const nos::trent& data, tc_scene* scene = nullptr);
};

/**
 * Get a white 1x1 texture handle (singleton).
 */
TextureHandle get_white_texture_handle();


/**
 * MaterialHandle - smart reference to material asset.
 *
 * Two modes:
 * 1. Direct - stores Material* directly
 * 2. Asset - stores MaterialAsset via nb::object
 */
class MaterialHandle {
public:
    // Direct material pointer (optional)
    Material* _direct = nullptr;

    // Python asset object (MaterialAsset or None)
    nb::object asset;

    MaterialHandle() : asset(nb::none()) {}

    explicit MaterialHandle(nb::object asset_) : _direct(nullptr), asset(std::move(asset_)) {}

    explicit MaterialHandle(Material* direct) : _direct(direct), asset(nb::none()) {}

    /**
     * Create handle from direct Material.
     */
    static MaterialHandle from_direct(Material* material) {
        return MaterialHandle(material);
    }

    /**
     * Create handle from Python MaterialAsset.
     */
    static MaterialHandle from_asset(nb::object asset) {
        return MaterialHandle(std::move(asset));
    }

    /**
     * Create handle by name lookup in ResourceManager.
     */
    static MaterialHandle from_name(const std::string& name);

    /**
     * Check if handle is valid (has direct material or asset).
     */
    bool is_valid() const {
        return _direct != nullptr || !asset.is_none();
    }

    /**
     * Check if this is a direct material (not from asset).
     */
    bool is_direct() const {
        return _direct != nullptr;
    }

    /**
     * Get asset name (empty if direct).
     */
    std::string name() const;

    /**
     * Get Material pointer.
     * Returns nullptr if handle is empty.
     */
    Material* get() const;

    /**
     * Get Material pointer, or error material if not available.
     */
    Material* get_material() const;

    /**
     * Get Material pointer or nullptr.
     */
    Material* get_material_or_none() const {
        return get();
    }

    /**
     * Serialize for scene saving.
     */
    nb::dict serialize() const;

    /**
     * Deserialize from scene data.
     */
    static MaterialHandle deserialize(const nb::dict& data);

    /**
     * Deserialize inplace from scene data.
     */
    void deserialize_from(const nos::trent& data, tc_scene* scene = nullptr);
};


// Forward declaration
class SkeletonData;

/**
 * SkeletonHandle - smart reference to skeleton asset.
 *
 * Wraps SkeletonAsset nb::object, provides:
 * - Access to SkeletonData
 * - Serialization/deserialization with UUID
 */
class SkeletonHandle {
public:
    // Direct skeleton pointer (optional, for non-asset skeletons)
    SkeletonData* _direct = nullptr;

    // Python asset object (SkeletonAsset or None)
    nb::object asset;

    SkeletonHandle() : asset(nb::none()) {}

    explicit SkeletonHandle(nb::object asset_) : _direct(nullptr), asset(std::move(asset_)) {}

    explicit SkeletonHandle(SkeletonData* direct) : _direct(direct), asset(nb::none()) {}

    // Create handle from direct SkeletonData pointer.
    static SkeletonHandle from_direct(SkeletonData* skeleton) {
        return SkeletonHandle(skeleton);
    }

    // Create handle by name lookup in ResourceManager.
    static SkeletonHandle from_name(const std::string& name);

    // Create handle from Python SkeletonAsset.
    static SkeletonHandle from_asset(nb::object asset) {
        return SkeletonHandle(std::move(asset));
    }

    // Check if handle is valid (has direct skeleton or asset).
    bool is_valid() const {
        return _direct != nullptr || !asset.is_none();
    }

    // Check if this is a direct skeleton (not from asset).
    bool is_direct() const {
        return _direct != nullptr;
    }

    /**
     * Get asset name.
     */
    std::string name() const {
        if (asset.is_none()) return "";
        return nb::cast<std::string>(asset.attr("name"));
    }

    /**
     * Get SkeletonData pointer.
     * Returns nullptr if asset is empty or resource is None.
     */
    SkeletonData* get() const;

    /**
     * Serialize for scene saving.
     */
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

    /**
     * Deserialize from scene data.
     */
    static SkeletonHandle deserialize(const nb::dict& data);

    /**
     * Deserialize inplace from scene data.
     */
    void deserialize_from(const nos::trent& data, tc_scene* scene = nullptr);
};

// Forward declaration
namespace animation {
class AnimationClip;
}

/**
 * AnimationClipHandle - smart reference to animation clip asset.
 *
 * Wraps AnimationClipAsset nb::object, provides:
 * - Access to AnimationClip
 * - Serialization/deserialization with UUID
 */
class AnimationClipHandle {
public:
    // Direct animation clip pointer (optional, for non-asset clips)
    animation::AnimationClip* _direct = nullptr;

    // Python asset object (AnimationClipAsset or None)
    nb::object asset;

    AnimationClipHandle() : asset(nb::none()) {}

    explicit AnimationClipHandle(nb::object asset_) : _direct(nullptr), asset(std::move(asset_)) {}

    explicit AnimationClipHandle(animation::AnimationClip* direct) : _direct(direct), asset(nb::none()) {}

    // Create handle from direct AnimationClip pointer.
    static AnimationClipHandle from_direct(animation::AnimationClip* clip) {
        return AnimationClipHandle(clip);
    }

    /**
     * Create handle by name lookup in ResourceManager.
     */
    static AnimationClipHandle from_name(const std::string& name);

    /**
     * Create handle from Python AnimationClipAsset.
     */
    static AnimationClipHandle from_asset(nb::object asset) {
        return AnimationClipHandle(std::move(asset));
    }

    /**
     * Create handle by UUID lookup in ResourceManager.
     */
    static AnimationClipHandle from_uuid(const std::string& uuid);

    // Check if handle is valid (has direct clip or asset).
    bool is_valid() const {
        return _direct != nullptr || !asset.is_none();
    }

    // Check if this is a direct clip (not from asset).
    bool is_direct() const {
        return _direct != nullptr;
    }

    // Get asset name (empty if direct).
    std::string name() const {
        if (asset.is_none()) return "";
        return nb::cast<std::string>(asset.attr("name"));
    }

    /**
     * Get AnimationClip pointer.
     * Returns nullptr if asset is empty or resource is None.
     */
    animation::AnimationClip* get() const;

    /**
     * Convenience alias.
     */
    animation::AnimationClip* clip() const { return get(); }

    /**
     * Serialize for scene saving.
     */
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

    /**
     * Deserialize from scene data.
     */
    static AnimationClipHandle deserialize(const nb::dict& data);

    /**
     * Deserialize inplace from scene data.
     */
    void deserialize_from(const nos::trent& data, tc_scene* scene = nullptr);
};

} // namespace termin

// Include inline implementations
#include "handles_inline.hpp"

// Additional handle types in separate files
#include "voxel_grid_handle.hpp"
