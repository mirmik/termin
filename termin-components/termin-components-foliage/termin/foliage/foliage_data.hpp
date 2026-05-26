#pragma once

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace termin {

struct FoliageVec3f {
public:
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
};

struct FoliageBounds3f {
public:
    FoliageVec3f min;
    FoliageVec3f max;
    bool valid = false;
};

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
};

class FoliageData {
public:
    std::string uuid;
    std::string name;
    std::string source_path;
    std::vector<FoliageInstance> instances;
    FoliageBounds3f local_bounds;
    uint32_t version = 0;
    bool loaded = false;

    FoliageData() = default;
    FoliageData(std::string uuid, std::string name, std::string source_path = {});

    bool load_from_file(const std::filesystem::path& path);
    bool save_to_file(const std::filesystem::path& path) const;
    void clear();
    void set_instances(std::vector<FoliageInstance> value);
    void add_instance(const FoliageInstance& instance);
    void remove_instance_at(size_t index);
    size_t remove_instances_in_radius(const FoliageVec3f& center, float radius);
    void recompute_bounds();
    size_t instance_count() const;
    bool empty() const;
};

} // namespace termin
