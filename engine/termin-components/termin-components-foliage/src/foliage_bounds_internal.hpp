#pragma once

#include <cstddef>
#include <span>

#include <termin/foliage/foliage_data.hpp>

namespace termin::foliage_detail {

    struct BoundsComputation {
        AABBf bounds{};
        size_t invalid_instance = 0;
        bool has_bounds = false;
        bool valid = true;
    };

    inline BoundsComputation compute_bounds(std::span<const FoliageInstance> instances) noexcept {
        BoundsComputation result;
        for (size_t index = 0; index < instances.size(); ++index) {
            const FoliageInstance& instance = instances[index];
            if (!instance.is_finite()) {
                result.invalid_instance = index;
                result.valid = false;
                return result;
            }

            const Vec3f position = instance.position();
            if (!result.has_bounds) {
                result.bounds = {position, position};
                result.has_bounds = true;
            } else {
                result.bounds.extend(position);
            }
        }
        return result;
    }

    inline bool bounds_equal(const AABBf& left, const AABBf& right) noexcept {
        return left.min_point == right.min_point && left.max_point == right.max_point;
    }

} // namespace termin::foliage_detail
