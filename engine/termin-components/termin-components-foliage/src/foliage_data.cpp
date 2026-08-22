#include <termin/foliage/foliage_data.hpp>

#include "foliage_bounds_internal.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <utility>

#include <tcbase/tc_log.h>
#include <termin/foliage/foliage_file.hpp>

namespace termin {

    FoliageData::FoliageData(std::string uuid_value, std::string name_value, std::string source_path_value)
        : uuid(std::move(uuid_value)),
          name(std::move(name_value)),
          source_path(std::move(source_path_value)) {}

    bool FoliageData::load_from_file(const std::filesystem::path& path) {
        FoliageFileResult result = load_foliage_file(path, *this);
        return result.ok;
    }

    bool FoliageData::save_to_file(const std::filesystem::path& path) const {
        FoliageFileResult result = save_foliage_file(path, *this);
        return result.ok;
    }

    void FoliageData::clear() {
        instances.clear();
        local_bounds = {};
        has_local_bounds = false;
        loaded = true;
        ++version;
    }

    bool FoliageData::set_instances(std::vector<FoliageInstance> value) {
        const foliage_detail::BoundsComputation computed = foliage_detail::compute_bounds(value);
        if (!computed.valid) {
            tc_log_error("[FoliageData] rejected non-finite foliage instance at index %zu", computed.invalid_instance);
            return false;
        }
        instances = std::move(value);
        local_bounds = computed.bounds;
        has_local_bounds = computed.has_bounds;
        loaded = true;
        ++version;
        return true;
    }

    bool FoliageData::add_instance(const FoliageInstance& instance) {
        if (!instance.is_finite()) {
            tc_log_error("[FoliageData] rejected non-finite foliage instance");
            return false;
        }
        const Vec3f position = instance.position();
        instances.push_back(instance);
        if (!has_local_bounds) {
            local_bounds = {position, position};
            has_local_bounds = true;
        } else {
            local_bounds.extend(position);
        }
        loaded = true;
        ++version;
        return true;
    }

    void FoliageData::remove_instance_at(size_t index) {
        if (index >= instances.size()) {
            return;
        }
        instances.erase(instances.begin() + static_cast<std::ptrdiff_t>(index));
        recompute_bounds();
        loaded = true;
        ++version;
    }

    size_t FoliageData::remove_instances_in_radius(const Vec3f& center, float radius) {
        if (!center.is_finite() || !std::isfinite(radius) || radius < 0.0f) {
            tc_log_error("[FoliageData] rejected non-finite center or invalid removal radius");
            return 0;
        }
        if (instances.empty()) {
            return 0;
        }

        const foliage_detail::BoundsComputation current = foliage_detail::compute_bounds(instances);
        if (!current.valid) {
            tc_log_error("[FoliageData] cannot remove by radius: non-finite instance at index %zu",
                         current.invalid_instance);
            return 0;
        }
        const size_t before = instances.size();
        const float radius_sq = radius * radius;
        if (!std::isfinite(radius_sq)) {
            tc_log_error("[FoliageData] removal radius is too large");
            return 0;
        }
        instances.erase(std::remove_if(instances.begin(),
                                       instances.end(),
                                       [&](const FoliageInstance& instance) {
                                           return (instance.position() - center).norm_squared() <= radius_sq;
                                       }),
                        instances.end());

        const size_t removed = before - instances.size();
        if (removed > 0) {
            recompute_bounds();
            loaded = true;
            ++version;
        }
        return removed;
    }

    bool FoliageData::recompute_bounds() {
        const foliage_detail::BoundsComputation computed = foliage_detail::compute_bounds(instances);
        if (!computed.valid) {
            local_bounds = {};
            has_local_bounds = false;
            tc_log_error("[FoliageData] cannot compute bounds: non-finite instance at index %zu",
                         computed.invalid_instance);
            return false;
        }
        local_bounds = computed.bounds;
        has_local_bounds = computed.has_bounds;
        return true;
    }

    size_t FoliageData::instance_count() const {
        return instances.size();
    }

    bool FoliageData::empty() const {
        return instances.empty();
    }

} // namespace termin
