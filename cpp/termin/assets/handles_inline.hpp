#pragma once

// Inline implementations for handle methods.
// Include this at the end of handles.hpp.
// These implementations use nb::module_::import, so they can be
// compiled in any module that includes handles.hpp.
//
// Note: MaterialHandle methods that access Material members are NOT inline
// because they would create circular dependencies. They are in handles.cpp.

#include "termin/skeleton/skeleton_data.hpp"
#include "termin/animation/animation_clip.hpp"
#include "termin/bindings/trent_helpers.hpp"
#include "tc_log.hpp"

namespace termin {

// ========== TextureHandle inline implementations ==========

inline TextureHandle TextureHandle::from_name(const std::string& name) {
    try {
        nb::object rm_module = nb::module_::import_("termin.assets.resources");
        nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
        nb::object asset = rm.attr("get_texture_asset")(name);
        if (asset.is_none()) {
            return TextureHandle();
        }
        return TextureHandle(asset);
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "TextureHandle::from_name('%s')", name.c_str());
        return TextureHandle();
    }
}

inline TextureHandle TextureHandle::from_file(
    const std::string& path,
    const std::string& name
) {
    try {
        nb::object texture_asset_module = nb::module_::import_("termin.visualization.render.texture_asset");
        nb::object TextureAsset = texture_asset_module.attr("TextureAsset");

        nb::object asset;
        if (name.empty()) {
            asset = TextureAsset.attr("from_file")(path);
        } else {
            asset = TextureAsset.attr("from_file")(path, nb::arg("name") = name);
        }
        return TextureHandle(asset);
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "TextureHandle::from_file('%s')", path.c_str());
        return TextureHandle();
    }
}

inline TextureHandle TextureHandle::from_texture_data(
    nb::object texture_data,
    const std::string& name
) {
    try {
        nb::object texture_asset_module = nb::module_::import_("termin.visualization.render.texture_asset");
        nb::object TextureAsset = texture_asset_module.attr("TextureAsset");

        nb::object asset = TextureAsset(
            nb::arg("texture_data") = texture_data,
            nb::arg("name") = name
        );
        return TextureHandle(asset);
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "TextureHandle::from_texture_data('%s')", name.c_str());
        return TextureHandle();
    }
}

inline TextureHandle TextureHandle::deserialize(const nb::dict& data) {
    if (data.contains("uuid")) {
        try {
            std::string uuid = nb::cast<std::string>(data["uuid"]);
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object asset = rm.attr("get_texture_asset_by_uuid")(uuid);
            if (!asset.is_none()) {
                return TextureHandle(asset);
            }
        } catch (const nb::python_error& e) {
            tc::Log::warn(e, "TextureHandle::deserialize uuid lookup");
        }
    }

    std::string type = data.contains("type") ? nb::cast<std::string>(data["type"]) : "none";

    if (type == "named") {
        std::string name = nb::cast<std::string>(data["name"]);
        return from_name(name);
    } else if (type == "path") {
        try {
            std::string path = nb::cast<std::string>(data["path"]);
            size_t last_slash = path.find_last_of("/\\");
            std::string filename = (last_slash != std::string::npos)
                ? path.substr(last_slash + 1) : path;
            size_t last_dot = filename.find_last_of('.');
            std::string name = (last_dot != std::string::npos)
                ? filename.substr(0, last_dot) : filename;
            return from_name(name);
        } catch (const nb::python_error& e) {
            tc::Log::warn(e, "TextureHandle::deserialize path lookup");
            return TextureHandle();
        }
    }

    return TextureHandle();
}

inline void TextureHandle::deserialize_from(const nos::trent& data, tc_scene*) {
    _direct = TcTexture();

    if (!data.is_dict()) {
        asset = nb::none();
        return;
    }

    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].as_string();
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object found = rm.attr("get_texture_asset_by_uuid")(uuid);
            if (!found.is_none()) {
                asset = found;
                return;
            }
        } catch (const std::exception& e) {
            tc::Log::warn(e, "TextureHandle::deserialize_from uuid lookup");
        }
    }

    std::string type = data.contains("type") ? data["type"].as_string() : "none";

    if (type == "named") {
        std::string name = data["name"].as_string();
        asset = from_name(name).asset;
    } else if (type == "path") {
        std::string path = data["path"].as_string();
        size_t last_slash = path.find_last_of("/\\");
        std::string filename = (last_slash != std::string::npos)
            ? path.substr(last_slash + 1) : path;
        size_t last_dot = filename.find_last_of('.');
        std::string name = (last_dot != std::string::npos)
            ? filename.substr(0, last_dot) : filename;
        asset = from_name(name).asset;
    } else {
        asset = nb::none();
    }
}

inline void TextureHandle::bind(GraphicsBackend* graphics, int unit, int64_t context_key) const {
    TextureGPU* gpu_ptr = gpu();
    TcTexture data = get();
    if (gpu_ptr == nullptr || !data.is_valid()) {
        return;
    }
    gpu_ptr->bind(graphics, data, version(), unit, context_key);
}

// ========== MaterialHandle inline implementations ==========
// Note: name(), get(), get_material(), serialize() are NOT inline
// because they need Material definition. See handles.cpp.

inline MaterialHandle MaterialHandle::from_name(const std::string& name) {
    try {
        nb::object rm_module = nb::module_::import_("termin.assets.resources");
        nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
        nb::object asset = rm.attr("get_material_asset")(name);
        if (asset.is_none()) {
            return MaterialHandle();
        }
        return MaterialHandle(asset);
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "MaterialHandle::from_name('%s')", name.c_str());
        return MaterialHandle();
    }
}

inline MaterialHandle MaterialHandle::deserialize(const nb::dict& data) {
    // Helper to create UnknownMaterial preserving original data for re-serialization
    auto create_unknown_material = [&data](const std::string& material_ref) -> MaterialHandle {
        try {
            nb::object unknown_mod = nb::module_::import_("termin.visualization.render.materials.unknown_material");
            nb::object UnknownMaterial = unknown_mod.attr("UnknownMaterial");
            nb::object unknown = UnknownMaterial.attr("for_missing_material")(material_ref, data);
            return MaterialHandle(unknown);
        } catch (const nb::python_error& e) {
            tc::Log::warn(e, "MaterialHandle::deserialize create_unknown_material");
            return MaterialHandle();
        }
    };

    if (data.contains("uuid")) {
        try {
            std::string uuid = nb::cast<std::string>(data["uuid"]);
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object asset = rm.attr("get_material_asset_by_uuid")(uuid);
            if (!asset.is_none()) {
                return MaterialHandle(asset);
            }
            // UUID not found - create UnknownMaterial with preserved data
            tc::Log::warn("MaterialHandle::deserialize: material with uuid '%s' not found", uuid.c_str());
            return create_unknown_material(uuid);
        } catch (const nb::python_error& e) {
            tc::Log::warn(e, "MaterialHandle::deserialize uuid lookup");
            return create_unknown_material("unknown");
        }
    }

    std::string type = data.contains("type") ? nb::cast<std::string>(data["type"]) : "none";

    if (type == "named") {
        std::string name = nb::cast<std::string>(data["name"]);
        MaterialHandle result = from_name(name);
        if (!result.is_valid()) {
            tc::Log::warn("MaterialHandle::deserialize: material '%s' not found", name.c_str());
            return create_unknown_material(name);
        }
        return result;
    } else if (type == "path") {
        try {
            std::string path = nb::cast<std::string>(data["path"]);
            size_t last_slash = path.find_last_of("/\\");
            std::string filename = (last_slash != std::string::npos)
                ? path.substr(last_slash + 1) : path;
            size_t last_dot = filename.find_last_of('.');
            std::string name = (last_dot != std::string::npos)
                ? filename.substr(0, last_dot) : filename;
            MaterialHandle result = from_name(name);
            if (!result.is_valid()) {
                tc::Log::warn("MaterialHandle::deserialize: material at path '%s' not found", path.c_str());
                return create_unknown_material(name);
            }
            return result;
        } catch (const nb::python_error& e) {
            tc::Log::warn(e, "MaterialHandle::deserialize path lookup");
            return create_unknown_material("unknown");
        }
    }

    return create_unknown_material("unknown");
}

inline void MaterialHandle::deserialize_from(const nos::trent& data, tc_scene*) {
    _direct = nullptr;

    // Helper to create UnknownMaterial preserving original data for re-serialization
    // We set asset to the UnknownMaterial object and leave _direct = nullptr
    // get_material() will resolve it through the asset later
    auto create_unknown_material = [this, &data](const std::string& material_ref) {
        try {
            // Convert trent to Python dict to preserve original data
            nb::object py_data = trent_to_py(data);
            nb::object unknown_mod = nb::module_::import_("termin.visualization.render.materials.unknown_material");
            nb::object UnknownMaterial = unknown_mod.attr("UnknownMaterial");
            nb::object unknown = UnknownMaterial.attr("for_missing_material")(material_ref, py_data);
            asset = unknown;
        } catch (const nb::python_error& e) {
            tc::Log::warn(e, "MaterialHandle::deserialize_from create_unknown_material");
            asset = nb::none();
        }
    };

    if (!data.is_dict()) {
        create_unknown_material("unknown");
        return;
    }

    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].as_string();
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object found = rm.attr("get_material_asset_by_uuid")(uuid);
            if (!found.is_none()) {
                asset = found;
                return;
            }
            // UUID not found - create UnknownMaterial with preserved data
            tc::Log::warn("MaterialHandle::deserialize_from: material with uuid '%s' not found", uuid.c_str());
            create_unknown_material(uuid);
            return;
        } catch (const std::exception& e) {
            tc::Log::warn(e, "MaterialHandle::deserialize_from uuid lookup");
            create_unknown_material("unknown");
            return;
        }
    }

    std::string type = data.contains("type") ? data["type"].as_string() : "none";

    if (type == "named") {
        std::string name = data["name"].as_string();
        MaterialHandle result = from_name(name);
        if (result.is_valid()) {
            asset = result.asset;
            _direct = result._direct;
        } else {
            tc::Log::warn("MaterialHandle::deserialize_from: material '%s' not found", name.c_str());
            create_unknown_material(name);
        }
    } else if (type == "path") {
        std::string path = data["path"].as_string();
        size_t last_slash = path.find_last_of("/\\");
        std::string filename = (last_slash != std::string::npos)
            ? path.substr(last_slash + 1) : path;
        size_t last_dot = filename.find_last_of('.');
        std::string name = (last_dot != std::string::npos)
            ? filename.substr(0, last_dot) : filename;
        MaterialHandle result = from_name(name);
        if (result.is_valid()) {
            asset = result.asset;
            _direct = result._direct;
        } else {
            tc::Log::warn("MaterialHandle::deserialize_from: material at path '%s' not found", path.c_str());
            create_unknown_material(name);
        }
    } else {
        create_unknown_material("unknown");
    }
}

// ========== SkeletonHandle inline implementations ==========

inline SkeletonHandle SkeletonHandle::from_name(const std::string& name) {
    try {
        nb::object rm_module = nb::module_::import_("termin.assets.resources");
        nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
        nb::object asset = rm.attr("get_skeleton_asset")(name);
        if (asset.is_none()) {
            return SkeletonHandle();
        }
        return SkeletonHandle(asset);
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "SkeletonHandle::from_name('%s')", name.c_str());
        return SkeletonHandle();
    }
}

inline SkeletonData* SkeletonHandle::get() const {
    if (_direct != nullptr) {
        return _direct;
    }
    if (asset.is_none()) return nullptr;
    nb::object res = asset.attr("resource");
    if (res.is_none()) return nullptr;
    return nb::cast<SkeletonData*>(res);
}

inline SkeletonHandle SkeletonHandle::deserialize(const nb::dict& data) {
    if (data.contains("uuid")) {
        try {
            std::string uuid = nb::cast<std::string>(data["uuid"]);
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object asset = rm.attr("get_skeleton_asset_by_uuid")(uuid);
            if (!asset.is_none()) {
                return SkeletonHandle(asset);
            }
        } catch (const nb::python_error& e) {
            tc::Log::warn(e, "SkeletonHandle::deserialize uuid lookup");
        }
    }

    std::string type = data.contains("type") ? nb::cast<std::string>(data["type"]) : "none";

    if (type == "named") {
        std::string name = nb::cast<std::string>(data["name"]);
        return from_name(name);
    } else if (type == "path") {
        try {
            std::string path = nb::cast<std::string>(data["path"]);
            size_t last_slash = path.find_last_of("/\\");
            std::string filename = (last_slash != std::string::npos)
                ? path.substr(last_slash + 1) : path;
            size_t last_dot = filename.find_last_of('.');
            std::string name = (last_dot != std::string::npos)
                ? filename.substr(0, last_dot) : filename;
            return from_name(name);
        } catch (const nb::python_error& e) {
            tc::Log::warn(e, "SkeletonHandle::deserialize path lookup");
            return SkeletonHandle();
        }
    }

    return SkeletonHandle();
}

inline void SkeletonHandle::deserialize_from(const nos::trent& data, tc_scene*) {
    _direct = nullptr;

    if (!data.is_dict()) {
        tc::Log::warn("[SkeletonHandle::deserialize_from] data is not dict");
        asset = nb::none();
        return;
    }

    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].as_string();
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object found = rm.attr("get_skeleton_asset_by_uuid")(uuid);
            if (!found.is_none()) {
                asset = found;
                return;
            }
            tc::Log::warn("[SkeletonHandle::deserialize_from] uuid '%s' not found", uuid.c_str());
        } catch (const std::exception& e) {
            tc::Log::warn(e, "SkeletonHandle::deserialize_from uuid lookup");
        }
    }

    std::string type = data.contains("type") ? data["type"].as_string() : "none";

    if (type == "named") {
        std::string name = data["name"].as_string();
        asset = from_name(name).asset;
    } else if (type == "path") {
        std::string path = data["path"].as_string();
        size_t last_slash = path.find_last_of("/\\");
        std::string filename = (last_slash != std::string::npos)
            ? path.substr(last_slash + 1) : path;
        size_t last_dot = filename.find_last_of('.');
        std::string name = (last_dot != std::string::npos)
            ? filename.substr(0, last_dot) : filename;
        asset = from_name(name).asset;
    } else {
        tc::Log::warn("[SkeletonHandle::deserialize_from] unknown type '%s'", type.c_str());
        asset = nb::none();
    }
}

// ========== get_white_texture_handle ==========

inline TextureHandle get_white_texture_handle() {
    // Use Python singleton instead of C++ static to ensure consistency across modules
    try {
        nb::object texture_handle_module = nb::module_::import_("termin.visualization.core.texture_handle");
        nb::object handle = texture_handle_module.attr("get_white_texture_handle")();
        return nb::cast<TextureHandle>(handle);
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "get_white_texture_handle");
        return TextureHandle();
    }
}

// ========== AnimationClipHandle inline implementations ==========

inline AnimationClipHandle AnimationClipHandle::from_name(const std::string& name) {
    try {
        nb::object rm_module = nb::module_::import_("termin.assets.resources");
        nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
        nb::object asset = rm.attr("get_animation_clip_asset")(name);
        if (asset.is_none()) {
            return AnimationClipHandle();
        }
        return AnimationClipHandle(asset);
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "AnimationClipHandle::from_name('%s')", name.c_str());
        return AnimationClipHandle();
    }
}

inline AnimationClipHandle AnimationClipHandle::from_uuid(const std::string& uuid) {
    try {
        nb::object rm_module = nb::module_::import_("termin.assets.resources");
        nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
        nb::object asset = rm.attr("get_animation_clip_asset_by_uuid")(uuid);
        if (asset.is_none()) {
            return AnimationClipHandle();
        }
        return AnimationClipHandle(asset);
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "AnimationClipHandle::from_uuid('%s')", uuid.c_str());
        return AnimationClipHandle();
    }
}

inline animation::AnimationClip* AnimationClipHandle::get() const {
    if (_direct != nullptr) {
        return _direct;
    }
    if (asset.is_none()) return nullptr;
    nb::object res = asset.attr("resource");
    if (res.is_none()) return nullptr;
    return nb::cast<animation::AnimationClip*>(res);
}

inline AnimationClipHandle AnimationClipHandle::deserialize(const nb::dict& data) {
    if (data.contains("uuid")) {
        try {
            std::string uuid = nb::cast<std::string>(data["uuid"]);
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object asset = rm.attr("get_animation_clip_asset_by_uuid")(uuid);
            if (!asset.is_none()) {
                return AnimationClipHandle(asset);
            }
        } catch (const nb::python_error& e) {
            tc::Log::warn(e, "AnimationClipHandle::deserialize uuid lookup");
        }
    }

    std::string type = data.contains("type") ? nb::cast<std::string>(data["type"]) : "none";

    if (type == "named") {
        std::string name = nb::cast<std::string>(data["name"]);
        return from_name(name);
    } else if (type == "path") {
        try {
            std::string path = nb::cast<std::string>(data["path"]);
            size_t last_slash = path.find_last_of("/\\");
            std::string filename = (last_slash != std::string::npos)
                ? path.substr(last_slash + 1) : path;
            size_t last_dot = filename.find_last_of('.');
            std::string name = (last_dot != std::string::npos)
                ? filename.substr(0, last_dot) : filename;
            return from_name(name);
        } catch (const nb::python_error& e) {
            tc::Log::warn(e, "AnimationClipHandle::deserialize path lookup");
            return AnimationClipHandle();
        }
    }

    return AnimationClipHandle();
}

inline void AnimationClipHandle::deserialize_from(const nos::trent& data, tc_scene*) {
    _direct = nullptr;

    if (!data.is_dict()) {
        asset = nb::none();
        return;
    }

    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].as_string();
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object found = rm.attr("get_animation_clip_asset_by_uuid")(uuid);
            if (!found.is_none()) {
                asset = found;
                return;
            }
        } catch (const std::exception& e) {
            tc::Log::warn(e, "AnimationClipHandle::deserialize_from uuid lookup");
        }
    }

    std::string type = data.contains("type") ? data["type"].as_string() : "none";

    if (type == "named") {
        std::string name = data["name"].as_string();
        asset = from_name(name).asset;
    } else if (type == "path") {
        std::string path = data["path"].as_string();
        size_t last_slash = path.find_last_of("/\\");
        std::string filename = (last_slash != std::string::npos)
            ? path.substr(last_slash + 1) : path;
        size_t last_dot = filename.find_last_of('.');
        std::string name = (last_dot != std::string::npos)
            ? filename.substr(0, last_dot) : filename;
        asset = from_name(name).asset;
    } else {
        asset = nb::none();
    }
}

} // namespace termin
