#pragma once

#include <string>
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>

#include "../../trent/trent.h"
#include "termin/render/handles.hpp"
#include "termin/render/mesh_gpu.hpp"
#include "termin/render/texture_gpu.hpp"
#include "termin/mesh/tc_mesh_handle.hpp"
#include "termin/assets/texture_data.hpp"

namespace nb = nanobind;

namespace termin {

// Forward declarations
class Material;

/**
 * MeshHandle - smart reference to mesh asset.
 *
 * Stores nb::object pointing to Python MeshAsset.
 * MeshAsset contains TcMesh (GPU-ready mesh registered in tc_mesh registry).
 *
 * Usage:
 *   auto handle = MeshHandle::from_name("Cube");
 *   if (auto* gpu = handle.gpu()) {
 *       gpu->draw();
 *   }
 */
class MeshHandle {
public:
    // Direct TcMesh (optional, for non-asset meshes)
    TcMesh _direct;

    // Python asset object (MeshAsset or None)
    nb::object asset;

    MeshHandle() : asset(nb::none()) {}

    explicit MeshHandle(nb::object asset_) : asset(std::move(asset_)) {}

    explicit MeshHandle(TcMesh direct) : _direct(std::move(direct)), asset(nb::none()) {}

    // Create handle from direct TcMesh.
    static MeshHandle from_direct(TcMesh mesh) {
        return MeshHandle(std::move(mesh));
    }

    /**
     * Create handle by name lookup in ResourceManager.
     */
    static MeshHandle from_name(const std::string& name);

    /**
     * Create handle from Python MeshAsset.
     */
    static MeshHandle from_asset(nb::object asset) {
        return MeshHandle(std::move(asset));
    }

    /**
     * Create handle from Mesh3 by creating a MeshAsset.
     */
    static MeshHandle from_mesh3(
        nb::object mesh,
        const std::string& name = "mesh",
        const std::string& source_path = ""
    );

    /**
     * Create handle from vertices and indices.
     */
    static MeshHandle from_vertices_indices(
        nb::ndarray<nb::numpy, float> vertices,
        nb::ndarray<nb::numpy, uint32_t> indices,
        const std::string& name = "mesh"
    );

    // Check if handle is valid (has direct mesh or asset).
    bool is_valid() const {
        return _direct.is_valid() || !asset.is_none();
    }

    // Check if this is a direct mesh (not from asset).
    bool is_direct() const {
        return _direct.is_valid();
    }

    // Get asset name (empty if direct).
    std::string name() const {
        if (asset.is_none()) return "";
        return nb::cast<std::string>(asset.attr("name"));
    }

    /**
     * Get version for change tracking.
     */
    int version() const {
        if (asset.is_none()) return 0;
        return nb::cast<int>(asset.attr("version"));
    }

    /**
     * Get Mesh3 data as nb::object (for Python interop).
     */
    nb::object mesh() const {
        if (asset.is_none()) return nb::none();
        return asset.attr("resource");
    }

    /**
     * Get TcMesh (GPU-ready mesh).
     * Returns invalid TcMesh if asset is empty or resource is None.
     */
    TcMesh get() const {
        if (_direct.is_valid()) {
            return _direct;
        }
        if (asset.is_none()) return TcMesh();
        nb::object res = asset.attr("resource");
        if (res.is_none()) return TcMesh();
        return nb::cast<TcMesh>(res);
    }

    /**
     * Get raw tc_mesh pointer.
     * Returns nullptr if mesh is invalid.
     */
    tc_mesh* raw() const {
        TcMesh m = get();
        return m.mesh;
    }

    /**
     * Get GPU handle for rendering.
     * Returns MeshGPU pointer or nullptr.
     */
    MeshGPU* gpu() const {
        if (asset.is_none()) return nullptr;
        nb::object gpu_obj = asset.attr("gpu");
        if (gpu_obj.is_none()) return nullptr;
        return nb::cast<MeshGPU*>(gpu_obj);
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
        // Also include path/name for debugging and fallback
        nb::object source_path = asset.attr("source_path");
        if (!source_path.is_none()) {
            d["type"] = "path";
            d["path"] = nb::str(source_path.attr("as_posix")());
        } else {
            d["type"] = "named";
            d["name"] = asset.attr("name");
        }
        return d;
    }

    /**
     * Deserialize from scene data.
     */
    static MeshHandle deserialize(const nb::dict& data);

    /**
     * Deserialize inplace from scene data.
     */
    void deserialize_from(const nos::trent& data);
};


/**
 * TextureHandle - smart reference to texture asset.
 *
 * Similar to MeshHandle but for textures.
 */
class TextureHandle {
public:
    // Direct texture data pointer (optional, for non-asset textures)
    TextureData* _direct = nullptr;

    // Python asset object (TextureAsset or None)
    nb::object asset;

    TextureHandle() : asset(nb::none()) {}

    explicit TextureHandle(nb::object asset_) : _direct(nullptr), asset(std::move(asset_)) {}

    explicit TextureHandle(TextureData* direct) : _direct(direct), asset(nb::none()) {}

    // Create handle from direct TextureData pointer.
    static TextureHandle from_direct(TextureData* texture_data) {
        return TextureHandle(texture_data);
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
     * Create handle from TextureData.
     */
    static TextureHandle from_texture_data(
        nb::object texture_data,
        const std::string& name = "texture"
    );

    // Check if handle is valid (has direct texture or asset).
    bool is_valid() const {
        return _direct != nullptr || !asset.is_none();
    }

    // Check if this is a direct texture (not from asset).
    bool is_direct() const {
        return _direct != nullptr;
    }

    // Get asset name (empty if direct).
    std::string name() const {
        if (asset.is_none()) return "";
        return nb::cast<std::string>(asset.attr("name"));
    }

    /**
     * Get version for change tracking.
     */
    int version() const {
        if (asset.is_none()) return 0;
        return nb::cast<int>(asset.attr("version"));
    }

    /**
     * Get TextureData resource pointer.
     * Returns nullptr if asset is empty or resource is None.
     */
    TextureData* get() const {
        if (_direct != nullptr) {
            return _direct;
        }
        if (asset.is_none()) return nullptr;
        nb::object res = asset.attr("resource");
        if (res.is_none()) return nullptr;
        return nb::cast<TextureData*>(res);
    }

    /**
     * Get GPU handle for rendering.
     * Returns TextureGPU pointer or nullptr.
     */
    TextureGPU* gpu() const {
        if (asset.is_none()) return nullptr;
        nb::object gpu_obj = asset.attr("gpu");
        if (gpu_obj.is_none()) return nullptr;
        return nb::cast<TextureGPU*>(gpu_obj);
    }

    /**
     * Convenience method: bind texture to unit.
     * Delegates to gpu()->bind() with texture data and version.
     */
    void bind(GraphicsBackend* graphics, int unit = 0, int64_t context_key = 0) const;

    /**
     * Get source path.
     */
    std::string source_path() const {
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
        // Also include path/name for debugging and fallback
        nb::object source_path = asset.attr("source_path");
        if (!source_path.is_none()) {
            d["type"] = "path";
            d["path"] = nb::str(source_path.attr("as_posix")());
        } else {
            d["type"] = "named";
            d["name"] = asset.attr("name");
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
    void deserialize_from(const nos::trent& data);
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
    void deserialize_from(const nos::trent& data);
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
        nb::object source_path = asset.attr("source_path");
        if (!source_path.is_none()) {
            d["type"] = "path";
            d["path"] = nb::str(source_path.attr("as_posix")());
        } else {
            d["type"] = "named";
            d["name"] = asset.attr("name");
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
    void deserialize_from(const nos::trent& data);
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
        nb::object source_path = asset.attr("source_path");
        if (!source_path.is_none()) {
            d["type"] = "path";
            d["path"] = nb::str(source_path.attr("as_posix")());
        } else {
            d["type"] = "named";
            d["name"] = asset.attr("name");
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
    void deserialize_from(const nos::trent& data);
};

} // namespace termin

// Include inline implementations
#include "handles_inline.hpp"

// Additional handle types in separate files
#include "voxel_grid_handle.hpp"
