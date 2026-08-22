#pragma once

#include <cstddef>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <string>
#include <type_traits>
#include <vector>

#include <termin/export.hpp>
#include <termin/geom/aabb.hpp>

namespace termin {

    struct FoliageInstance {
    public:
        float px = 0.0f;
        float py = 0.0f;
        float pz = 0.0f;
        float nx = 0.0f;
        float ny = 0.0f;
        float nz = 1.0f;
        float yaw = 0.0f;
        float scale = 1.0f;
        uint32_t variant = 0;
        uint32_t seed = 0;

        Vec3f position() const noexcept {
            return {px, py, pz};
        }

        bool is_finite() const noexcept {
            return position().is_finite() && Vec3f{nx, ny, nz}.is_finite() && std::isfinite(yaw) &&
                   std::isfinite(scale);
        }
    };

    static_assert(std::is_standard_layout_v<FoliageInstance>);
    static_assert(std::is_trivially_copyable_v<FoliageInstance>);
    static_assert(sizeof(FoliageInstance) == 40);
    static_assert(offsetof(FoliageInstance, px) == 0);
    static_assert(offsetof(FoliageInstance, nx) == 12);
    static_assert(offsetof(FoliageInstance, yaw) == 24);
    static_assert(offsetof(FoliageInstance, variant) == 32);
    static_assert(offsetof(FoliageInstance, seed) == 36);

    class ENTITY_API FoliageData {
    public:
        std::string uuid;
        std::string name;
        std::string source_path;
        std::vector<FoliageInstance> instances;
        AABBf local_bounds;
        bool has_local_bounds = false;
        uint32_t version = 0;
        bool loaded = false;

        FoliageData() = default;
        FoliageData(std::string uuid, std::string name, std::string source_path = {});

        bool load_from_file(const std::filesystem::path& path);
        bool save_to_file(const std::filesystem::path& path) const;
        void clear();
        bool set_instances(std::vector<FoliageInstance> value);
        bool add_instance(const FoliageInstance& instance);
        void remove_instance_at(size_t index);
        size_t remove_instances_in_radius(const Vec3f& center, float radius);
        bool recompute_bounds();
        size_t instance_count() const;
        bool empty() const;
    };

} // namespace termin
