// tc_scene_render_ext.cpp - Engine-level render lifecycle helpers for TcSceneRef.
#include <termin/scene/tc_scene_render_ext.hpp>

#include <termin/entity/entity.hpp>
#include <tcbase/tc_log.hpp>

extern "C" {
#include "core/tc_component.h"
#include "core/tc_scene_extension.h"
#include "core/tc_scene_extension_ids.h"
#include "core/tc_scene_render_mount.h"
#include "core/tc_scene_render_state.h"
#include <termin_collision/termin_collision.h>
}

namespace termin {

void register_default_scene_extensions() {
    tc_scene_render_mount_extension_init();
    tc_scene_render_state_extension_init();
    termin_collision_runtime_init();
}

std::vector<tc_scene_ext_type_id> default_scene_extension_ids() {
    std::vector<tc_scene_ext_type_id> extensions = {
        TC_SCENE_EXT_TYPE_RENDER_MOUNT,
        TC_SCENE_EXT_TYPE_RENDER_STATE,
    };

    if (tc_scene_ext_is_registered(TC_SCENE_EXT_TYPE_COLLISION_WORLD)) {
        extensions.push_back(TC_SCENE_EXT_TYPE_COLLISION_WORLD);
    }

    return extensions;
}

TcSceneRef create_scene_with_extensions(
    const std::string& name,
    const std::string& uuid,
    const std::vector<tc_scene_ext_type_id>& extensions
) {
    TcSceneRef scene = TcSceneRef::create(name, uuid);
    tc_scene_handle h = scene.handle();

    if (tc_scene_handle_valid(h)) {
        for (tc_scene_ext_type_id type_id : extensions) {
            if (!tc_scene_ext_attach(h, type_id)) {
                tc::Log::error("[create_scene_with_extensions] failed to attach scene extension %llu",
                               (unsigned long long)type_id);
            }
        }
    }

    return scene;
}

TcSceneRef create_scene_with_render(const std::string& name, const std::string& uuid) {
    return create_scene_with_extensions(name, uuid, default_scene_extension_ids());
}

TcSceneRef deserialize_scene_with_render(const nos::trent& data, const std::string& name) {
    TcSceneRef scene = create_scene_with_render(name, "");

    if (!scene.valid()) {
        tc::Log::error("[deserialize_scene_with_render] failed to create render-enabled scene '%s'",
                       name.c_str());
        return scene;
    }

    if (data.contains("uuid") && data["uuid"].is_string()) {
        scene.set_uuid(data["uuid"].as_string());
    }

    nos::trent load_data = data;
    nos::trent merged_extensions;
    if (load_data.contains("extensions") && load_data["extensions"].is_dict()) {
        merged_extensions = load_data["extensions"];
    }
    if (!merged_extensions.is_dict()) {
        merged_extensions.init(nos::trent::type::dict);
    }

    scene_merge_legacy_render_extensions(load_data, merged_extensions);
    if (!merged_extensions.as_dict().empty()) {
        load_data["extensions"] = std::move(merged_extensions);
    }

    scene.load_from_data(load_data, true);
    return scene;
}

} // namespace termin
