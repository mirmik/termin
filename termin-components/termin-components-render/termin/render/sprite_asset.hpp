#pragma once

#include <cstdint>
#include <memory>
#include <string>

#include <termin/export.hpp>

namespace termin {

enum class SpriteSampling : uint8_t {
    Linear = 0,
    Nearest = 1,
};

struct SpriteRegion {
    int32_t x = 0;
    int32_t y = 0;
    int32_t width = 0;
    int32_t height = 0;
};

struct SpriteAsset {
    std::string uuid;
    std::string name;
    std::string source_path;
    std::string texture_uuid;
    SpriteRegion region;
    int32_t source_width = 0;
    int32_t source_height = 0;
    float pivot_x = 0.5f;
    float pivot_y = 0.5f;
    float pixels_per_unit = 100.0f;
    SpriteSampling sampling = SpriteSampling::Linear;
    uint32_t version = 0;
    bool loaded = false;
};

class ENTITY_API TcSpriteAsset {
public:
    std::shared_ptr<SpriteAsset> ptr;

    TcSpriteAsset() = default;
    explicit TcSpriteAsset(std::shared_ptr<SpriteAsset> asset);

    bool is_valid() const;
    bool is_loaded() const;
    SpriteAsset* get() const;
    const char* uuid() const;
    const char* name() const;
    uint32_t version() const;
    void unload();

    bool update(
        const std::string& texture_uuid,
        SpriteRegion region,
        int32_t source_width,
        int32_t source_height,
        float pivot_x,
        float pivot_y,
        float pixels_per_unit,
        SpriteSampling sampling);

    static TcSpriteAsset declare(
        const std::string& uuid,
        const std::string& name,
        const std::string& source_path = {});
    static TcSpriteAsset from_uuid(const std::string& uuid);
    static void clear_registry_for_tests();
};

} // namespace termin
