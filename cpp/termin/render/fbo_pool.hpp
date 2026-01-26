// fbo_pool.hpp - FBO pool for managing framebuffer allocation
#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <memory>

#include "termin/render/graphics_backend.hpp"

namespace termin {

// FBO Pool entry (move-only because of unique_ptr)
struct FBOPoolEntry {
    std::string key;
    FramebufferHandlePtr fbo;
    int width = 0;
    int height = 0;
    int samples = 1;
    std::string format;
    bool external = false;

    FBOPoolEntry() = default;
    FBOPoolEntry(FBOPoolEntry&&) = default;
    FBOPoolEntry& operator=(FBOPoolEntry&&) = default;
    FBOPoolEntry(const FBOPoolEntry&) = delete;
    FBOPoolEntry& operator=(const FBOPoolEntry&) = delete;
};

// FBO Pool - manages framebuffer allocation and reuse
class FBOPool {
public:
    std::vector<FBOPoolEntry> entries;
    std::unordered_map<std::string, std::string> alias_to_canonical;

    FramebufferHandle* ensure(
        GraphicsBackend* graphics,
        const std::string& key,
        int width,
        int height,
        int samples = 1,
        const std::string& format = ""
    );

    FramebufferHandle* get(const std::string& key);
    void set(const std::string& key, FramebufferHandle* fbo);
    void add_alias(const std::string& alias, const std::string& canonical);
    void clear();

    std::vector<std::string> keys() const;
};

} // namespace termin
