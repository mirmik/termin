#include <termin/foliage/foliage_data.hpp>

#include <algorithm>
#include <cstddef>
#include <utility>

#include <termin/foliage/foliage_file.hpp>

namespace termin {

FoliageData::FoliageData(std::string uuid_value, std::string name_value, std::string source_path_value)
    : uuid(std::move(uuid_value))
    , name(std::move(name_value))
    , source_path(std::move(source_path_value))
{
}

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
    local_bounds = FoliageBounds3f{};
    loaded = true;
    ++version;
}

void FoliageData::set_instances(std::vector<FoliageInstance> value) {
    instances = std::move(value);
    recompute_bounds();
    loaded = true;
    ++version;
}

void FoliageData::add_instance(const FoliageInstance& instance) {
    instances.push_back(instance);
    if (!local_bounds.valid) {
        local_bounds.min = {instance.px, instance.py, instance.pz};
        local_bounds.max = local_bounds.min;
        local_bounds.valid = true;
    } else {
        local_bounds.min.x = std::min(local_bounds.min.x, instance.px);
        local_bounds.min.y = std::min(local_bounds.min.y, instance.py);
        local_bounds.min.z = std::min(local_bounds.min.z, instance.pz);
        local_bounds.max.x = std::max(local_bounds.max.x, instance.px);
        local_bounds.max.y = std::max(local_bounds.max.y, instance.py);
        local_bounds.max.z = std::max(local_bounds.max.z, instance.pz);
    }
    loaded = true;
    ++version;
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

size_t FoliageData::remove_instances_in_radius(const FoliageVec3f& center, float radius) {
    if (radius < 0.0f || instances.empty()) {
        return 0;
    }

    const size_t before = instances.size();
    const float radius_sq = radius * radius;
    instances.erase(
        std::remove_if(
            instances.begin(),
            instances.end(),
            [&](const FoliageInstance& instance) {
                const float dx = instance.px - center.x;
                const float dy = instance.py - center.y;
                const float dz = instance.pz - center.z;
                return dx * dx + dy * dy + dz * dz <= radius_sq;
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

void FoliageData::recompute_bounds() {
    local_bounds = FoliageBounds3f{};
    if (instances.empty()) {
        return;
    }

    const FoliageInstance& first = instances.front();
    local_bounds.min = {first.px, first.py, first.pz};
    local_bounds.max = local_bounds.min;
    local_bounds.valid = true;
    for (const FoliageInstance& instance : instances) {
        local_bounds.min.x = std::min(local_bounds.min.x, instance.px);
        local_bounds.min.y = std::min(local_bounds.min.y, instance.py);
        local_bounds.min.z = std::min(local_bounds.min.z, instance.pz);
        local_bounds.max.x = std::max(local_bounds.max.x, instance.px);
        local_bounds.max.y = std::max(local_bounds.max.y, instance.py);
        local_bounds.max.z = std::max(local_bounds.max.z, instance.pz);
    }
}

size_t FoliageData::instance_count() const {
    return instances.size();
}

bool FoliageData::empty() const {
    return instances.empty();
}

} // namespace termin
