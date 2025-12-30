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

namespace termin {

// ========== MeshHandle inline implementations ==========

inline MeshHandle MeshHandle::from_name(const std::string& name) {
    try {
        nb::object rm_module = nb::module_::import_("termin.assets.resources");
        nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
        nb::object asset = rm.attr("get_mesh_asset")(name);
        if (asset.is_none()) {
            return MeshHandle();
        }
        return MeshHandle(asset);
    } catch (const nb::python_error& e) {
        fprintf(stderr, "[ERROR] MeshHandle::from_name('%s') failed: %s\n", name.c_str(), e.what());
        return MeshHandle();
    }
}

inline MeshHandle MeshHandle::from_mesh3(
    nb::object mesh,
    const std::string& name,
    const std::string& source_path
) {
    try {
        nb::object mesh_asset_module = nb::module_::import_("termin.visualization.core.mesh_asset");
        nb::object MeshAsset = mesh_asset_module.attr("MeshAsset");

        nb::object asset;
        if (source_path.empty()) {
            asset = MeshAsset(
                nb::arg("mesh_data") = mesh,
                nb::arg("name") = name
            );
        } else {
            asset = MeshAsset(
                nb::arg("mesh_data") = mesh,
                nb::arg("name") = name,
                nb::arg("source_path") = source_path
            );
        }
        return MeshHandle(asset);
    } catch (const nb::python_error& e) {
        fprintf(stderr, "[ERROR] MeshHandle::from_mesh3('%s') failed: %s\n", name.c_str(), e.what());
        return MeshHandle();
    }
}

inline MeshHandle MeshHandle::from_vertices_indices(
    nb::ndarray<nb::numpy, float> vertices,
    nb::ndarray<nb::numpy, uint32_t> indices,
    const std::string& name
) {
    try {
        nb::object mesh_module = nb::module_::import_("termin.mesh.mesh");
        nb::object Mesh3 = mesh_module.attr("Mesh3");
        nb::object mesh = Mesh3(
            nb::arg("vertices") = vertices,
            nb::arg("triangles") = indices,
            nb::arg("name") = name
        );
        return from_mesh3(mesh, name);
    } catch (const nb::python_error& e) {
        fprintf(stderr, "[ERROR] MeshHandle::from_vertices_indices failed: %s\n", e.what());
        return MeshHandle();
    }
}

inline MeshHandle MeshHandle::deserialize(const nb::dict& data) {
    if (data.contains("uuid")) {
        try {
            std::string uuid = nb::cast<std::string>(data["uuid"]);
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object handle = rm.attr("get_mesh_by_uuid")(uuid);
            if (!handle.is_none()) {
                return nb::cast<MeshHandle>(handle);
            }
        } catch (const nb::python_error&) {}
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
        } catch (const nb::python_error&) {
            return MeshHandle();
        }
    }

    return MeshHandle();
}

inline void MeshHandle::deserialize_from(const nos::trent& data) {
    if (!data.is_dict()) {
        asset = nb::none();
        return;
    }

    // Try UUID first
    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].as_string();
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object handle = rm.attr("get_mesh_by_uuid")(uuid);
            if (!handle.is_none()) {
                asset = nb::cast<MeshHandle>(handle).asset;
                return;
            }
        } catch (...) {}
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
    } catch (const nb::python_error&) {
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
    } catch (const nb::python_error&) {
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
    } catch (const nb::python_error&) {
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
        } catch (const nb::python_error&) {}
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
        } catch (const nb::python_error&) {
            return TextureHandle();
        }
    }

    return TextureHandle();
}

inline void TextureHandle::deserialize_from(const nos::trent& data) {
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
        } catch (...) {}
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
    TextureData* data = get();
    if (gpu_ptr == nullptr || data == nullptr) {
        return;
    }
    gpu_ptr->bind(graphics, *data, version(), unit, context_key);
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
    } catch (const nb::python_error&) {
        return MaterialHandle();
    }
}

inline MaterialHandle MaterialHandle::deserialize(const nb::dict& data) {
    if (data.contains("uuid")) {
        try {
            std::string uuid = nb::cast<std::string>(data["uuid"]);
            nb::object rm_module = nb::module_::import_("termin.assets.resources");
            nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
            nb::object asset = rm.attr("get_material_asset_by_uuid")(uuid);
            if (!asset.is_none()) {
                return MaterialHandle(asset);
            }
        } catch (const nb::python_error&) {}
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
        } catch (const nb::python_error&) {
            return MaterialHandle();
        }
    }

    return MaterialHandle();
}

inline void MaterialHandle::deserialize_from(const nos::trent& data) {
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
            nb::object found = rm.attr("get_material_asset_by_uuid")(uuid);
            if (!found.is_none()) {
                asset = found;
                return;
            }
        } catch (...) {}
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
    } catch (const nb::python_error&) {
        return SkeletonHandle();
    }
}

inline SkeletonData* SkeletonHandle::get() const {
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
        } catch (const nb::python_error&) {}
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
        } catch (const nb::python_error&) {
            return SkeletonHandle();
        }
    }

    return SkeletonHandle();
}

inline void SkeletonHandle::deserialize_from(const nos::trent& data) {
    if (!data.is_dict()) {
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
        } catch (...) {}
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

// ========== get_white_texture_handle ==========

inline TextureHandle get_white_texture_handle() {
    // Use Python singleton instead of C++ static to ensure consistency across modules
    try {
        nb::object texture_handle_module = nb::module_::import_("termin.visualization.core.texture_handle");
        nb::object handle = texture_handle_module.attr("get_white_texture_handle")();
        return nb::cast<TextureHandle>(handle);
    } catch (const nb::python_error&) {
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
    } catch (const nb::python_error&) {
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
    } catch (const nb::python_error&) {
        return AnimationClipHandle();
    }
}

inline animation::AnimationClip* AnimationClipHandle::get() const {
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
        } catch (const nb::python_error&) {}
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
        } catch (const nb::python_error&) {
            return AnimationClipHandle();
        }
    }

    return AnimationClipHandle();
}

inline void AnimationClipHandle::deserialize_from(const nos::trent& data) {
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
        } catch (...) {}
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
