#include "texture_gpu.hpp"
#include "graphics_backend.hpp"

namespace termin {

void TextureGPU::bind(
    GraphicsBackend* graphics,
    const TcTexture& texture,
    int version,
    int unit,
    int64_t context_key
) {
    // Check if we need to re-upload
    if (uploaded_version != version) {
        invalidate();
        uploaded_version = version;
    }

    // Upload to this context if needed
    auto it = handles.find(context_key);
    if (it == handles.end()) {
        auto [data, w, h] = texture.get_upload_data();
        // create_texture returns unique_ptr, convert to shared_ptr
        auto handle = std::shared_ptr<GPUTextureHandle>(
            graphics->create_texture(data.data(), w, h, texture.channels()).release()
        );
        it = handles.emplace(context_key, std::move(handle)).first;
    }

    // Bind
    it->second->bind(unit);
}

void TextureGPU::invalidate() {
    // Release all handles
    handles.clear();
}

} // namespace termin
