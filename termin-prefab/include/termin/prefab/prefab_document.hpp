#pragma once

#include <string>

#include <trent/trent.h>
#include <termin/entity/entity.hpp>
#include <termin/prefab/export.hpp>

namespace termin::prefab {

enum class PrefabDocumentError {
    None = 0,
    InvalidJson,
    InvalidDocument,
    UnsupportedVersion,
    InvalidTargetScene,
    InvalidParent,
    SourceMaterializationFailed,
};

struct PrefabDocumentResult;

class TERMIN_PREFAB_API PrefabDocument {
public:
    static constexpr const char* CurrentVersion = "3.0";

    static PrefabDocumentResult parse_json(const std::string& json);
    static PrefabDocumentResult capture(
        const std::string& asset_uuid,
        const Entity& editable_root
    );
    static PrefabDocumentResult empty(
        const std::string& asset_uuid,
        const std::string& root_source_id,
        const std::string& root_name
    );

    bool valid() const;
    const std::string& asset_uuid() const { return _asset_uuid; }
    const nos::trent& source_hierarchy() const { return _root; }
    std::string source_revision() const;
    std::string to_json(int indent = 2) const;

    PrefabDocumentResult validate() const;
    PrefabDocumentResult materialize_source(
        tc_scene_handle target_scene,
        const Entity& parent = Entity()
    ) const;

private:
    std::string _asset_uuid;
    nos::trent _root;
};

struct PrefabDocumentResult {
    PrefabDocument document;
    Entity root;
    PrefabDocumentError error = PrefabDocumentError::None;
    std::string message;

    bool ok() const { return error == PrefabDocumentError::None; }
};

} // namespace termin::prefab
