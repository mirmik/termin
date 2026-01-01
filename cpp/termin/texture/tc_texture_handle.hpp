#pragma once

// TcTexture - RAII wrapper for tc_texture* (image data with transforms)
// Registers texture data in tc_texture C registry.

extern "C" {
#include "termin_core.h"
}

#include <string>
#include <cstring>
#include <vector>
#include <cstdint>
#include <tuple>

namespace termin {

// TcTexture - texture wrapper with registry integration
// Manages tc_texture* with reference counting
class TcTexture {
public:
    tc_texture* texture = nullptr;

    TcTexture() = default;

    explicit TcTexture(tc_texture* t) : texture(t) {
        if (texture) tc_texture_add_ref(texture);
    }

    TcTexture(const TcTexture& other) : texture(other.texture) {
        if (texture) tc_texture_add_ref(texture);
    }

    TcTexture(TcTexture&& other) noexcept : texture(other.texture) {
        other.texture = nullptr;
    }

    TcTexture& operator=(const TcTexture& other) {
        if (this != &other) {
            if (texture) tc_texture_release(texture);
            texture = other.texture;
            if (texture) tc_texture_add_ref(texture);
        }
        return *this;
    }

    TcTexture& operator=(TcTexture&& other) noexcept {
        if (this != &other) {
            if (texture) tc_texture_release(texture);
            texture = other.texture;
            other.texture = nullptr;
        }
        return *this;
    }

    ~TcTexture() {
        if (texture) {
            tc_texture_release(texture);
            texture = nullptr;
        }
    }

    // Query
    bool is_valid() const { return texture != nullptr; }
    const char* uuid() const { return texture ? texture->uuid : ""; }
    const char* name() const { return texture && texture->name ? texture->name : ""; }
    uint32_t version() const { return texture ? texture->version : 0; }
    uint32_t width() const { return texture ? texture->width : 0; }
    uint32_t height() const { return texture ? texture->height : 0; }
    uint8_t channels() const { return texture ? texture->channels : 0; }
    const void* data() const { return texture ? texture->data : nullptr; }
    size_t data_size() const {
        return texture ? (size_t)texture->width * texture->height * texture->channels : 0;
    }

    // Transform flags
    bool flip_x() const { return texture && texture->flip_x; }
    bool flip_y() const { return texture && texture->flip_y; }
    bool transpose() const { return texture && texture->transpose; }

    const char* source_path() const {
        return texture && texture->source_path ? texture->source_path : "";
    }

    void bump_version() {
        if (texture) texture->version++;
    }

    // Set texture data
    bool set_data(
        const void* pixel_data,
        uint32_t w,
        uint32_t h,
        uint8_t ch,
        const std::string& tex_name = "",
        const std::string& src_path = ""
    ) {
        if (!texture) return false;
        return tc_texture_set_data(
            texture,
            pixel_data,
            w, h, ch,
            tex_name.empty() ? nullptr : tex_name.c_str(),
            src_path.empty() ? nullptr : src_path.c_str()
        );
    }

    // Set transform flags
    void set_transforms(bool fx, bool fy, bool trans) {
        if (texture) {
            tc_texture_set_transforms(texture, fx, fy, trans);
        }
    }

    // Create TcTexture from raw pixel data
    static TcTexture from_data(
        const void* pixel_data,
        uint32_t width,
        uint32_t height,
        uint8_t channels = 4,
        bool flip_x = false,
        bool flip_y = true,
        bool transpose = false,
        const std::string& name = "",
        const std::string& source_path = "",
        const std::string& uuid_hint = ""
    );

    // Create 1x1 white texture
    static TcTexture white_1x1();

    // Get by UUID from registry
    static TcTexture from_uuid(const std::string& uuid) {
        tc_texture* t = tc_texture_get(uuid.c_str());
        return TcTexture(t);
    }

    // Get or create by UUID
    static TcTexture get_or_create(const std::string& uuid) {
        tc_texture* t = tc_texture_get_or_create(uuid.c_str());
        return TcTexture(t);
    }

    // Get transformed data for GPU upload
    // Returns new buffer with transforms applied, plus final width and height
    std::tuple<std::vector<uint8_t>, uint32_t, uint32_t> get_upload_data() const;
};

} // namespace termin
