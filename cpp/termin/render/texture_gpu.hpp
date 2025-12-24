#pragma once

#include <unordered_map>
#include <memory>
#include <cstdint>

#include "termin/render/handles.hpp"

namespace termin {

// Forward declarations
class GraphicsBackend;
class TextureData;

/**
 * TextureGPU - GPU resource wrapper for texture rendering.
 *
 * Manages GPU textures with:
 * - Version tracking for automatic re-upload
 * - Multi-context support (multiple GL contexts)
 */
class TextureGPU {
public:
    // Uploaded version (-1 = never uploaded)
    int uploaded_version = -1;

    // GPU handles per context (shared_ptr for pybind11 compatibility)
    std::unordered_map<int64_t, std::shared_ptr<GPUTextureHandle>> handles;

    TextureGPU() = default;
    ~TextureGPU() = default;

    // Non-copyable (owns GPU resources)
    TextureGPU(const TextureGPU&) = delete;
    TextureGPU& operator=(const TextureGPU&) = delete;

    // Movable
    TextureGPU(TextureGPU&&) = default;
    TextureGPU& operator=(TextureGPU&&) = default;

    /**
     * Check if any GPU data is uploaded.
     */
    bool is_uploaded() const {
        return !handles.empty();
    }

    /**
     * Bind texture to unit, uploading/re-uploading if needed.
     *
     * @param graphics Graphics backend for GPU operations
     * @param texture_data TextureData with pixel data
     * @param version Current version of texture data
     * @param unit Texture unit to bind to
     * @param context_key GL context key
     */
    void bind(
        GraphicsBackend* graphics,
        const TextureData& texture_data,
        int version,
        int unit = 0,
        int64_t context_key = 0
    );

    /**
     * Invalidate all GPU handles (e.g., when version changes).
     */
    void invalidate();

    /**
     * Explicitly delete all GPU resources.
     */
    void delete_resources() {
        invalidate();
        uploaded_version = -1;
    }
};

} // namespace termin
