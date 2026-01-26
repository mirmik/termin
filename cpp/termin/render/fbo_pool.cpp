// fbo_pool.cpp - FBO pool implementation
#include "fbo_pool.hpp"
#include "tc_log.hpp"

namespace termin {

FramebufferHandle* FBOPool::ensure(
    GraphicsBackend* graphics,
    const std::string& key,
    int width,
    int height,
    int samples,
    const std::string& format
) {
    // Find existing entry
    for (auto& entry : entries) {
        if (entry.key == key) {
            // Resize if needed
            if (entry.fbo && (entry.width != width || entry.height != height)) {
                entry.fbo->resize(width, height);
                entry.width = width;
                entry.height = height;
            }
            return entry.fbo.get();
        }
    }

    // Create new entry
    if (!graphics) {
        tc::Log::error("FBOPool::ensure: graphics is null");
        return nullptr;
    }

    auto fbo = graphics->create_framebuffer(width, height, samples, format);
    if (!fbo) {
        tc::Log::error("FBOPool::ensure: failed to create framebuffer '%s'", key.c_str());
        return nullptr;
    }

    FramebufferHandle* ptr = fbo.get();

    FBOPoolEntry entry;
    entry.key = key;
    entry.fbo = std::move(fbo);
    entry.width = width;
    entry.height = height;
    entry.samples = samples;
    entry.format = format;
    entry.external = false;
    entries.push_back(std::move(entry));

    return ptr;
}

FramebufferHandle* FBOPool::get(const std::string& key) {
    // First, try direct lookup
    for (auto& entry : entries) {
        if (entry.key == key) {
            return entry.fbo.get();
        }
    }
    // Try alias lookup
    auto alias_it = alias_to_canonical.find(key);
    if (alias_it != alias_to_canonical.end()) {
        for (auto& entry : entries) {
            if (entry.key == alias_it->second) {
                return entry.fbo.get();
            }
        }
    }
    return nullptr;
}

void FBOPool::set(const std::string& key, FramebufferHandle* fbo) {
    for (auto& entry : entries) {
        if (entry.key == key) {
            // Don't destroy external FBO
            entry.fbo.reset();
            entry.external = true;
            return;
        }
    }

    // Create new external entry
    FBOPoolEntry entry;
    entry.key = key;
    entry.fbo.reset();
    entry.external = true;
    entries.push_back(std::move(entry));
}

void FBOPool::add_alias(const std::string& alias, const std::string& canonical) {
    if (alias == canonical) return;  // No point in aliasing to itself
    alias_to_canonical[alias] = canonical;
}

void FBOPool::clear() {
    entries.clear();
    alias_to_canonical.clear();
}

std::vector<std::string> FBOPool::keys() const {
    std::vector<std::string> result;
    result.reserve(entries.size() + alias_to_canonical.size());
    for (const auto& entry : entries) {
        result.push_back(entry.key);
    }
    // Also include aliases
    for (const auto& pair : alias_to_canonical) {
        result.push_back(pair.first);
    }
    return result;
}

} // namespace termin
