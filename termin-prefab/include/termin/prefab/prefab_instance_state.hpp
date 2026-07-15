#pragma once

#include <cstdint>
#include <string>
#include <utility>
#include <vector>

#include <termin/entity/component.hpp>
#include <termin/prefab/export.hpp>

namespace termin::prefab {

class TERMIN_PREFAB_API PrefabInstanceState : public CxxComponent {
public:
    static constexpr const char* TypeName = "PrefabInstanceState";

    PrefabInstanceState();
    explicit PrefabInstanceState(std::string prefab_asset_uuid);

    static void register_type();

    const std::string& prefab_asset_uuid() const { return _prefab_asset_uuid; }
    void set_prefab_asset_uuid(std::string value) { _prefab_asset_uuid = std::move(value); }

    const std::string& source_revision() const { return _source_revision; }
    void set_source_revision(std::string value) { _source_revision = std::move(value); }

    void set_entity_mapping(
        std::vector<std::string> source_ids,
        std::vector<Entity> runtime_entities
    );
    void set_component_mapping(
        std::vector<std::string> source_ids,
        std::vector<Entity> runtime_owners
    );

    Entity entity_for_source(const std::string& source_id) const;
    Entity component_owner_for_source(const std::string& source_id) const;
    size_t entity_mapping_count() const;
    size_t component_mapping_count() const;
    bool mapping_valid() const { return _mapping_valid; }

    void on_added() override;

private:
    bool validate_mapping(bool require_live_references, std::string& message) const;

    std::string _prefab_asset_uuid;
    std::string _source_revision;
    std::vector<std::string> _source_entity_ids;
    std::vector<Entity> _runtime_entities;
    std::vector<std::string> _source_component_ids;
    std::vector<Entity> _component_owners;
    bool _mapping_valid = true;
};

TERMIN_PREFAB_API void register_prefab_component_types();

// Scene APIs are single-owner-thread APIs. These queries return a mutation-safe
// snapshot of live generational handles but do not add cross-thread safety.
TERMIN_PREFAB_API std::vector<Entity> find_live_prefab_instances(
    const std::string& prefab_asset_uuid
);
TERMIN_PREFAB_API std::vector<Entity> find_live_prefab_instances(
    tc_scene_handle scene,
    const std::string& prefab_asset_uuid
);
TERMIN_PREFAB_API size_t count_live_prefab_instances(
    const std::string& prefab_asset_uuid
);

} // namespace termin::prefab
