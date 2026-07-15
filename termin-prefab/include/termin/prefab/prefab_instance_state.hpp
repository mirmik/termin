#pragma once

#include <cstdint>
#include <string>
#include <utility>
#include <vector>

#include <termin/entity/component.hpp>
#include <termin/prefab/export.hpp>
#include <termin/prefab/prefab_override_value.hpp>

namespace termin::prefab {

class PrefabDocument;

enum class PrefabPropertyApplyError {
    None = 0,
    InvalidState,
    InvalidDocument,
    DocumentMismatch,
    OverrideNotFound,
    SourceEntityNotFound,
    RuntimeEntityNotFound,
    SourceComponentNotFound,
    RuntimeComponentNotFound,
    ComponentOwnerMismatch,
    ComponentTypeMismatch,
    FieldNotFound,
    FieldNotSerializable,
    KindMismatch,
    InvalidSourceValue,
    ResourceResolutionFailed,
    SetterFailed,
    StructuralOverrideInvalid,
    FactoryUnavailable,
    AttachmentFailed,
    ParentCycle,
    OrderFailed,
    RemovalConflict,
};

using PrefabOverrideRestoreError = PrefabPropertyApplyError;

enum class PrefabReconcilePhase {
    Validation = 0,
    Structure,
    SourceValue,
    OverrideValue,
};

struct TERMIN_PREFAB_API PrefabOverrideRestoreFailure {
    PrefabPropertyApplyError error = PrefabPropertyApplyError::None;
    std::string source_entity_id;
    std::string source_component_id;
    std::string field_path;
    std::string message;
};

struct TERMIN_PREFAB_API PrefabOverrideRestoreResult {
    size_t requested_count = 0;
    size_t restored_count = 0;
    std::vector<PrefabOverrideRestoreFailure> failures;

    bool ok() const { return failures.empty(); }
};

struct TERMIN_PREFAB_API PrefabReconcileFailure {
    PrefabReconcilePhase phase = PrefabReconcilePhase::Validation;
    PrefabPropertyApplyError error = PrefabPropertyApplyError::None;
    std::string source_entity_id;
    std::string source_component_id;
    std::string field_path;
    std::string message;
};

struct TERMIN_PREFAB_API PrefabReconcileResult {
    size_t structure_operation_count = 0;
    size_t structure_operations_applied = 0;
    size_t source_field_count = 0;
    size_t source_fields_applied = 0;
    size_t override_count = 0;
    size_t overrides_applied = 0;
    size_t dormant_override_count = 0;
    bool revision_updated = false;
    std::string previous_revision;
    std::string target_revision;
    std::vector<PrefabReconcileFailure> failures;

    bool ok() const { return failures.empty(); }
};

enum class PrefabStructuralOverrideKind {
    SuppressEntity = 0,
    SuppressComponent,
    PlaceEntity,
    PlaceComponent,
};

enum class PrefabStructureReferenceKind {
    End = 0,
    Source,
    Local,
};

struct TERMIN_PREFAB_API PrefabStructureReference {
    PrefabStructureReferenceKind kind = PrefabStructureReferenceKind::End;
    std::string source_id;
    Entity local_entity;
    std::string local_component_source_id;
};

struct TERMIN_PREFAB_API PrefabStructuralOverride {
    PrefabStructuralOverrideKind kind = PrefabStructuralOverrideKind::SuppressEntity;
    std::string source_entity_id;
    std::string source_component_id;
    PrefabStructureReference parent;
    PrefabStructureReference before;
};

struct TERMIN_PREFAB_API PrefabPropertyOverride {
    std::string source_entity_id;
    std::string source_component_id;
    std::string field_path;
    std::string target_kind;
    PrefabOverrideValue value;
};

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
    std::string source_for_entity(const Entity& runtime_entity) const;
    std::string source_for_component(
        const Entity& runtime_owner,
        const std::string& runtime_component_source_id
    ) const;
    bool rebind_entity_mapping(
        const std::string& source_id,
        const Entity& runtime_entity,
        std::string& error
    );
    bool rebind_component_mapping(
        const std::string& source_id,
        const Entity& runtime_owner,
        std::string& error
    );
    size_t entity_mapping_count() const;
    size_t component_mapping_count() const;
    bool mapping_valid() const {
        return _mapping_valid && _overrides_valid && _structural_overrides_valid;
    }

    bool set_property_override(PrefabPropertyOverride property_override, std::string& error);
    PrefabOverrideRestoreResult clear_property_override(
        const PrefabDocument& source,
        const std::string& source_entity_id,
        const std::string& source_component_id,
        const std::string& field_path
    );
    PrefabOverrideRestoreResult clear_all_property_overrides(
        const PrefabDocument& source
    );
    PrefabReconcileResult reconcile_properties(
        const PrefabDocument& source,
        const PrefabOverrideResourceResolver* resource_resolver = nullptr
    );
    PrefabReconcileResult reconcile(
        const PrefabDocument& source,
        const PrefabOverrideResourceResolver* resource_resolver = nullptr
    );
    bool set_structural_override(
        PrefabStructuralOverride structural_override,
        std::string& error
    );
    bool discard_structural_override(
        PrefabStructuralOverrideKind kind,
        const std::string& source_id
    );
    const std::vector<PrefabStructuralOverride>& structural_overrides() const {
        return _structural_overrides;
    }
    size_t structural_override_count() const { return _structural_overrides.size(); }
    bool structural_overrides_valid() const { return _structural_overrides_valid; }
    bool source_entity_suppressed(const std::string& source_id) const;
    // Explicit metadata-only escape hatch for repair/migration tools. Normal
    // editing must use clear_* so live values and metadata cannot diverge.
    bool discard_property_override(
        const std::string& source_entity_id,
        const std::string& source_component_id,
        const std::string& field_path
    );
    void discard_all_property_overrides();
    const PrefabPropertyOverride* property_override(
        const std::string& source_entity_id,
        const std::string& source_component_id,
        const std::string& field_path
    ) const;
    const PrefabStructuralOverride* structural_override(
        PrefabStructuralOverrideKind kind,
        const std::string& source_id
    ) const;
    const std::vector<PrefabPropertyOverride>& property_overrides() const {
        return _property_overrides;
    }
    size_t property_override_count() const { return _property_overrides.size(); }
    bool overrides_valid() const { return _overrides_valid; }

    tc_value serialize_data() const override;
    void deserialize_data(
        const tc_value* data,
        tc_scene_handle scene = TC_SCENE_HANDLE_INVALID
    ) override;

    void on_added() override;

private:
    bool validate_mapping(bool require_live_references, std::string& message) const;
    void reconcile_structure(
        const PrefabDocument& source,
        PrefabReconcileResult& result
    );

    std::string _prefab_asset_uuid;
    std::string _source_revision;
    std::vector<std::string> _source_entity_ids;
    std::vector<Entity> _runtime_entities;
    std::vector<std::string> _source_component_ids;
    std::vector<Entity> _component_owners;
    std::vector<PrefabPropertyOverride> _property_overrides;
    std::vector<PrefabStructuralOverride> _structural_overrides;
    tc::trent _invalid_serialized_overrides;
    tc::trent _invalid_serialized_structural_overrides;
    bool _mapping_valid = true;
    bool _overrides_valid = true;
    bool _structural_overrides_valid = true;
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
