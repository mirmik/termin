#pragma once

#include <filesystem>
#include <memory>
#include <string>

#include <termin/foliage/foliage_data.hpp>

namespace termin {

class ENTITY_API TcFoliageData {
public:
    std::shared_ptr<FoliageData> ptr;

    TcFoliageData() = default;
    explicit TcFoliageData(std::shared_ptr<FoliageData> data);

    bool is_valid() const;
    bool is_loaded() const;
    bool ensure_loaded() const;
    bool reload() const;

    FoliageData* get() const;
    const char* uuid() const;
    const char* name() const;
    const char* source_path() const;
    uint32_t version() const;
    size_t instance_count() const;

    static TcFoliageData declare(
        const std::string& uuid,
        const std::string& name,
        const std::string& source_path = {}
    );
    static TcFoliageData from_uuid(const std::string& uuid);
    static void clear_registry_for_tests();
};

} // namespace termin

