#pragma once

#include <string>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

#include "termin/render/handles.hpp"
#include "termin/render/mesh_gpu.hpp"
#include "termin/render/texture_gpu.hpp"
#include "termin/mesh/mesh3.hpp"
#include "termin/assets/texture_data.hpp"

namespace py = pybind11;

namespace termin {

// Forward declarations
class Material;

/**
 * MeshHandle - smart reference to mesh asset.
 *
 * Stores py::object pointing to Python MeshAsset.
 * Provides access to:
 * - Mesh3 data (via asset.resource)
 * - GPUMeshHandle for rendering (via asset.gpu)
 * - Version for change tracking (via asset.version)
 *
 * Usage:
 *   auto handle = MeshHandle::from_name("Cube");
 *   if (auto* gpu = handle.gpu()) {
 *       gpu->draw();
 *   }
 */
class MeshHandle {
public:
    // Python asset object (MeshAsset or None)
    py::object asset;

    MeshHandle() : asset(py::none()) {}

    explicit MeshHandle(py::object asset_) : asset(std::move(asset_)) {}

    /**
     * Create handle by name lookup in ResourceManager.
     */
    static MeshHandle from_name(const std::string& name);

    /**
     * Create handle from Python MeshAsset.
     */
    static MeshHandle from_asset(py::object asset) {
        return MeshHandle(std::move(asset));
    }

    /**
     * Create handle from Mesh3 by creating a MeshAsset.
     */
    static MeshHandle from_mesh3(
        py::object mesh,
        const std::string& name = "mesh",
        const std::string& source_path = ""
    );

    /**
     * Create handle from vertices and indices.
     */
    static MeshHandle from_vertices_indices(
        py::array_t<float> vertices,
        py::array_t<uint32_t> indices,
        const std::string& name = "mesh"
    );

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
     * Get version for change tracking.
     */
    int version() const {
        if (asset.is_none()) return 0;
        return asset.attr("version").cast<int>();
    }

    /**
     * Get Mesh3 data as py::object (for Python interop).
     */
    py::object mesh() const {
        if (asset.is_none()) return py::none();
        return asset.attr("resource");
    }

    /**
     * Get Mesh3 data pointer.
     * Returns nullptr if asset is empty or resource is None.
     */
    Mesh3* get() const {
        if (asset.is_none()) return nullptr;
        py::object res = asset.attr("resource");
        if (res.is_none()) return nullptr;
        return res.cast<Mesh3*>();
    }

    /**
     * Get GPU handle for rendering.
     * Returns MeshGPU pointer or nullptr.
     */
    MeshGPU* gpu() const {
        if (asset.is_none()) return nullptr;
        py::object gpu_obj = asset.attr("gpu");
        if (gpu_obj.is_none()) return nullptr;
        return gpu_obj.cast<MeshGPU*>();
    }

    /**
     * Serialize for scene saving.
     */
    py::dict serialize() const {
        if (asset.is_none()) {
            py::dict d;
            d["type"] = "none";
            return d;
        }
        py::object source_path = asset.attr("source_path");
        if (!source_path.is_none()) {
            py::dict d;
            d["type"] = "path";
            d["path"] = py::str(source_path.attr("as_posix")());
            return d;
        }
        py::dict d;
        d["type"] = "named";
        d["name"] = asset.attr("name");
        return d;
    }

    /**
     * Deserialize from scene data.
     */
    static MeshHandle deserialize(const py::dict& data);
};


/**
 * TextureHandle - smart reference to texture asset.
 *
 * Similar to MeshHandle but for textures.
 */
class TextureHandle {
public:
    // Python asset object (TextureAsset or None)
    py::object asset;

    TextureHandle() : asset(py::none()) {}

    explicit TextureHandle(py::object asset_) : asset(std::move(asset_)) {}

    /**
     * Create handle by name lookup in ResourceManager.
     */
    static TextureHandle from_name(const std::string& name);

    /**
     * Create handle from Python TextureAsset.
     */
    static TextureHandle from_asset(py::object asset) {
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
        py::object texture_data,
        const std::string& name = "texture"
    );

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
     * Get version for change tracking.
     */
    int version() const {
        if (asset.is_none()) return 0;
        return asset.attr("version").cast<int>();
    }

    /**
     * Get TextureData resource pointer.
     * Returns nullptr if asset is empty or resource is None.
     */
    TextureData* get() const {
        if (asset.is_none()) return nullptr;
        py::object res = asset.attr("resource");
        if (res.is_none()) return nullptr;
        return res.cast<TextureData*>();
    }

    /**
     * Get GPU handle for rendering.
     * Returns TextureGPU pointer or nullptr.
     */
    TextureGPU* gpu() const {
        if (asset.is_none()) return nullptr;
        py::object gpu_obj = asset.attr("gpu");
        if (gpu_obj.is_none()) return nullptr;
        return gpu_obj.cast<TextureGPU*>();
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
        py::object sp = asset.attr("source_path");
        if (sp.is_none()) return "";
        return py::str(sp.attr("as_posix")()).cast<std::string>();
    }

    /**
     * Serialize for scene saving.
     */
    py::dict serialize() const {
        if (asset.is_none()) {
            py::dict d;
            d["type"] = "none";
            return d;
        }
        py::object source_path = asset.attr("source_path");
        if (!source_path.is_none()) {
            py::dict d;
            d["type"] = "path";
            d["path"] = py::str(source_path.attr("as_posix")());
            return d;
        }
        py::dict d;
        d["type"] = "named";
        d["name"] = asset.attr("name");
        return d;
    }

    /**
     * Deserialize from scene data.
     */
    static TextureHandle deserialize(const py::dict& data);
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
 * 2. Asset - stores MaterialAsset via py::object
 */
class MaterialHandle {
public:
    // Direct material pointer (optional)
    Material* _direct = nullptr;

    // Python asset object (MaterialAsset or None)
    py::object asset;

    MaterialHandle() : asset(py::none()) {}

    explicit MaterialHandle(py::object asset_) : _direct(nullptr), asset(std::move(asset_)) {}

    explicit MaterialHandle(Material* direct) : _direct(direct), asset(py::none()) {}

    /**
     * Create handle from direct Material.
     */
    static MaterialHandle from_direct(Material* material) {
        return MaterialHandle(material);
    }

    /**
     * Create handle from Python MaterialAsset.
     */
    static MaterialHandle from_asset(py::object asset) {
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
    py::dict serialize() const;

    /**
     * Deserialize from scene data.
     */
    static MaterialHandle deserialize(const py::dict& data);
};

} // namespace termin
