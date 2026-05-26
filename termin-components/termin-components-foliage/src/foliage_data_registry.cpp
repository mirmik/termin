#include <termin/foliage/foliage_data_registry.hpp>

#include <mutex>
#include <unordered_map>
#include <utility>

#include <tcbase/tc_log.h>

namespace termin {
namespace {

std::mutex& foliage_registry_mutex() {
    static std::mutex mutex;
    return mutex;
}

std::unordered_map<std::string, std::shared_ptr<FoliageData>>& foliage_registry() {
    static std::unordered_map<std::string, std::shared_ptr<FoliageData>> registry;
    return registry;
}

} // namespace

TcFoliageData::TcFoliageData(std::shared_ptr<FoliageData> data)
    : ptr(std::move(data))
{
}

bool TcFoliageData::is_valid() const {
    return ptr != nullptr && !ptr->uuid.empty();
}

bool TcFoliageData::is_loaded() const {
    return is_valid() && ptr->loaded;
}

bool TcFoliageData::ensure_loaded() const {
    if (!is_valid()) {
        tc_log_warn("[FoliageData] ensure_loaded called on invalid handle");
        return false;
    }
    if (is_loaded()) {
        return true;
    }
    if (ptr->source_path.empty()) {
        tc_log_warn("[FoliageData] asset has no source path uuid=%s", ptr->uuid.c_str());
        return false;
    }
    if (!ptr->load_from_file(ptr->source_path)) {
        tc_log_error("[FoliageData] failed to load '%s' uuid=%s",
                     ptr->source_path.c_str(), ptr->uuid.c_str());
        return false;
    }
    return true;
}

bool TcFoliageData::reload() const {
    if (!is_valid()) {
        tc_log_warn("[FoliageData] reload called on invalid handle");
        return false;
    }
    if (ptr->source_path.empty()) {
        tc_log_warn("[FoliageData] cannot reload asset without source path uuid=%s", ptr->uuid.c_str());
        return false;
    }
    if (!ptr->load_from_file(ptr->source_path)) {
        tc_log_error("[FoliageData] failed to reload '%s' uuid=%s",
                     ptr->source_path.c_str(), ptr->uuid.c_str());
        return false;
    }
    return true;
}

FoliageData* TcFoliageData::get() const {
    return ptr.get();
}

const char* TcFoliageData::uuid() const {
    return is_valid() ? ptr->uuid.c_str() : "";
}

const char* TcFoliageData::name() const {
    return is_valid() ? ptr->name.c_str() : "";
}

const char* TcFoliageData::source_path() const {
    return is_valid() ? ptr->source_path.c_str() : "";
}

uint32_t TcFoliageData::version() const {
    return is_valid() ? ptr->version : 0;
}

size_t TcFoliageData::instance_count() const {
    return is_valid() ? ptr->instance_count() : 0;
}

TcFoliageData TcFoliageData::declare(
    const std::string& uuid,
    const std::string& name,
    const std::string& source_path
) {
    if (uuid.empty()) {
        tc_log_error("[FoliageData] cannot declare asset with empty uuid");
        return TcFoliageData();
    }

    std::lock_guard<std::mutex> lock(foliage_registry_mutex());
    auto& registry = foliage_registry();
    auto it = registry.find(uuid);
    if (it != registry.end()) {
        if (!name.empty()) {
            it->second->name = name;
        }
        if (!source_path.empty()) {
            it->second->source_path = source_path;
        }
        return TcFoliageData(it->second);
    }

    auto data = std::make_shared<FoliageData>(uuid, name.empty() ? uuid : name, source_path);
    registry[uuid] = data;
    return TcFoliageData(std::move(data));
}

TcFoliageData TcFoliageData::from_uuid(const std::string& uuid) {
    if (uuid.empty()) {
        return TcFoliageData();
    }
    std::lock_guard<std::mutex> lock(foliage_registry_mutex());
    auto& registry = foliage_registry();
    auto it = registry.find(uuid);
    if (it == registry.end()) {
        return TcFoliageData();
    }
    return TcFoliageData(it->second);
}

void TcFoliageData::clear_registry_for_tests() {
    std::lock_guard<std::mutex> lock(foliage_registry_mutex());
    foliage_registry().clear();
}

} // namespace termin
