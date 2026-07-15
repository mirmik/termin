#pragma once

#include <string>

#include <trent/trent.h>
#include <termin/entity/entity.hpp>
#include <termin/prefab/export.hpp>

namespace termin::prefab {

enum class PrefabInstantiateError {
    None = 0,
    InvalidDocument,
    InvalidTargetScene,
    InvalidParent,
    DuplicateSourceUuid,
    HierarchyCreationFailed,
};

struct PrefabInstantiateOptions {
    std::string root_name;
    bool has_position = false;
    double position[3] = {0.0, 0.0, 0.0};
};

struct PrefabInstantiateResult {
    Entity root;
    PrefabInstantiateError error = PrefabInstantiateError::None;
    std::string message;

    bool ok() const { return error == PrefabInstantiateError::None && root.valid(); }
};

class TERMIN_PREFAB_API PrefabInstantiator {
public:
    static PrefabInstantiateResult instantiate(
        const nos::trent& source_hierarchy,
        tc_scene_handle target_scene,
        const Entity& parent = Entity(),
        const PrefabInstantiateOptions& options = {}
    );
};

} // namespace termin::prefab
