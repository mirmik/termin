#include <termin/render/sprite_asset.hpp>

#include <cmath>
#include <mutex>
#include <unordered_map>
#include <utility>

#include <tcbase/tc_log.h>

namespace termin {
namespace {

std::mutex& sprite_registry_mutex() {
    static std::mutex mutex;
    return mutex;
}

std::unordered_map<std::string, std::shared_ptr<SpriteAsset>>& sprite_registry() {
    static std::unordered_map<std::string, std::shared_ptr<SpriteAsset>> registry;
    return registry;
}

bool valid_region(const SpriteRegion& region) {
    return region.x >= 0 && region.y >= 0 &&
           region.width > 0 && region.height > 0;
}

} // namespace

TcSpriteAsset::TcSpriteAsset(std::shared_ptr<SpriteAsset> asset)
    : ptr(std::move(asset))
{
}

bool TcSpriteAsset::is_valid() const {
    return ptr != nullptr && !ptr->uuid.empty();
}

bool TcSpriteAsset::is_loaded() const {
    return is_valid() && ptr->loaded;
}

SpriteAsset* TcSpriteAsset::get() const {
    return ptr.get();
}

const char* TcSpriteAsset::uuid() const {
    return is_valid() ? ptr->uuid.c_str() : "";
}

const char* TcSpriteAsset::name() const {
    return is_valid() ? ptr->name.c_str() : "";
}

uint32_t TcSpriteAsset::version() const {
    return is_valid() ? ptr->version : 0;
}

void TcSpriteAsset::unload() {
    if (!is_valid()) {
        tc_log_error("[SpriteAsset] cannot unload an invalid asset handle");
        return;
    }
    ptr->loaded = false;
    ++ptr->version;
}

bool TcSpriteAsset::update(
    const std::string& texture_uuid,
    SpriteRegion region,
    int32_t source_width,
    int32_t source_height,
    float pivot_x,
    float pivot_y,
    float pixels_per_unit,
    SpriteSampling sampling)
{
    if (!is_valid()) {
        tc_log_error("[SpriteAsset] cannot update an invalid asset handle");
        return false;
    }
    if (texture_uuid.empty()) {
        tc_log_error("[SpriteAsset] texture UUID is empty for sprite '%s'", ptr->uuid.c_str());
        return false;
    }
    if (!valid_region(region)) {
        tc_log_error(
            "[SpriteAsset] invalid region (%d, %d, %d, %d) for sprite '%s'",
            region.x, region.y, region.width, region.height, ptr->uuid.c_str());
        return false;
    }
    if (source_width <= 0 || source_height <= 0 ||
        region.x + region.width > source_width ||
        region.y + region.height > source_height) {
        tc_log_error(
            "[SpriteAsset] region exceeds source size %dx%d for sprite '%s'",
            source_width, source_height, ptr->uuid.c_str());
        return false;
    }
    if (!std::isfinite(pivot_x) || !std::isfinite(pivot_y) ||
        pivot_x < 0.0f || pivot_x > 1.0f ||
        pivot_y < 0.0f || pivot_y > 1.0f) {
        tc_log_error("[SpriteAsset] pivot must be normalized for sprite '%s'", ptr->uuid.c_str());
        return false;
    }
    if (!std::isfinite(pixels_per_unit) || pixels_per_unit <= 0.0f) {
        tc_log_error("[SpriteAsset] pixels_per_unit must be positive for sprite '%s'",
                     ptr->uuid.c_str());
        return false;
    }

    ptr->texture_uuid = texture_uuid;
    ptr->region = region;
    ptr->source_width = source_width;
    ptr->source_height = source_height;
    ptr->pivot_x = pivot_x;
    ptr->pivot_y = pivot_y;
    ptr->pixels_per_unit = pixels_per_unit;
    ptr->sampling = sampling;
    ptr->loaded = true;
    ++ptr->version;
    return true;
}

TcSpriteAsset TcSpriteAsset::declare(
    const std::string& uuid,
    const std::string& name,
    const std::string& source_path)
{
    if (uuid.empty()) {
        tc_log_error("[SpriteAsset] cannot declare asset with empty UUID");
        return {};
    }

    std::lock_guard<std::mutex> lock(sprite_registry_mutex());
    auto& registry = sprite_registry();
    auto it = registry.find(uuid);
    if (it != registry.end()) {
        if (!name.empty()) {
            it->second->name = name;
        }
        if (!source_path.empty()) {
            it->second->source_path = source_path;
        }
        return TcSpriteAsset(it->second);
    }

    auto asset = std::make_shared<SpriteAsset>();
    asset->uuid = uuid;
    asset->name = name.empty() ? uuid : name;
    asset->source_path = source_path;
    registry.emplace(uuid, asset);
    return TcSpriteAsset(std::move(asset));
}

TcSpriteAsset TcSpriteAsset::from_uuid(const std::string& uuid) {
    if (uuid.empty()) {
        return {};
    }
    std::lock_guard<std::mutex> lock(sprite_registry_mutex());
    auto it = sprite_registry().find(uuid);
    return it == sprite_registry().end() ? TcSpriteAsset{} : TcSpriteAsset{it->second};
}

void TcSpriteAsset::clear_registry_for_tests() {
    std::lock_guard<std::mutex> lock(sprite_registry_mutex());
    sprite_registry().clear();
}

} // namespace termin
