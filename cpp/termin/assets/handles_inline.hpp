#pragma once

// Inline implementations for handle methods.
// Include this at the end of handles.hpp.
// These implementations use py::module_::import, so they can be
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
        py::object rm_module = py::module_::import("termin.assets.resources");
        py::object rm = rm_module.attr("ResourceManager").attr("instance")();
        py::object asset = rm.attr("get_mesh_asset")(name);
        if (asset.is_none()) {
            return MeshHandle();
        }
        return MeshHandle(asset);
    } catch (const py::error_already_set& e) {
        fprintf(stderr, "[ERROR] MeshHandle::from_name('%s') failed: %s\n", name.c_str(), e.what());
        return MeshHandle();
    }
}

inline MeshHandle MeshHandle::from_mesh3(
    py::object mesh,
    const std::string& name,
    const std::string& source_path
) {
    try {
        py::object mesh_asset_module = py::module_::import("termin.visualization.core.mesh_asset");
        py::object MeshAsset = mesh_asset_module.attr("MeshAsset");

        py::object asset;
        if (source_path.empty()) {
            asset = MeshAsset(
                py::arg("mesh_data") = mesh,
                py::arg("name") = name
            );
        } else {
            asset = MeshAsset(
                py::arg("mesh_data") = mesh,
                py::arg("name") = name,
                py::arg("source_path") = source_path
            );
        }
        return MeshHandle(asset);
    } catch (const py::error_already_set& e) {
        fprintf(stderr, "[ERROR] MeshHandle::from_mesh3('%s') failed: %s\n", name.c_str(), e.what());
        return MeshHandle();
    }
}

inline MeshHandle MeshHandle::from_vertices_indices(
    py::array_t<float> vertices,
    py::array_t<uint32_t> indices,
    const std::string& name
) {
    try {
        py::object mesh_module = py::module_::import("termin.mesh.mesh");
        py::object Mesh3 = mesh_module.attr("Mesh3");
        py::object mesh = Mesh3(
            py::arg("vertices") = vertices,
            py::arg("triangles") = indices,
            py::arg("name") = name
        );
        return from_mesh3(mesh, name);
    } catch (const py::error_already_set& e) {
        fprintf(stderr, "[ERROR] MeshHandle::from_vertices_indices failed: %s\n", e.what());
        return MeshHandle();
    }
}

inline MeshHandle MeshHandle::deserialize(const py::dict& data) {
    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].cast<std::string>();
            py::object rm_module = py::module_::import("termin.assets.resources");
            py::object rm = rm_module.attr("ResourceManager").attr("instance")();
            py::object handle = rm.attr("get_mesh_by_uuid")(uuid);
            if (!handle.is_none()) {
                return handle.cast<MeshHandle>();
            }
        } catch (const py::error_already_set&) {}
    }

    std::string type = data.contains("type") ? data["type"].cast<std::string>() : "none";

    if (type == "named") {
        std::string name = data["name"].cast<std::string>();
        return from_name(name);
    } else if (type == "path") {
        try {
            std::string path = data["path"].cast<std::string>();
            size_t last_slash = path.find_last_of("/\\");
            std::string filename = (last_slash != std::string::npos)
                ? path.substr(last_slash + 1) : path;
            size_t last_dot = filename.find_last_of('.');
            std::string name = (last_dot != std::string::npos)
                ? filename.substr(0, last_dot) : filename;
            return from_name(name);
        } catch (const py::error_already_set&) {
            return MeshHandle();
        }
    }

    return MeshHandle();
}

inline void MeshHandle::deserialize_from(const nos::trent& data) {
    if (!data.is_dict()) {
        asset = py::none();
        return;
    }

    // Try UUID first
    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].as_string();
            py::object rm_module = py::module_::import("termin.assets.resources");
            py::object rm = rm_module.attr("ResourceManager").attr("instance")();
            py::object handle = rm.attr("get_mesh_by_uuid")(uuid);
            if (!handle.is_none()) {
                asset = handle.cast<MeshHandle>().asset;
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
        asset = py::none();
    }
}

// ========== TextureHandle inline implementations ==========

inline TextureHandle TextureHandle::from_name(const std::string& name) {
    try {
        py::object rm_module = py::module_::import("termin.assets.resources");
        py::object rm = rm_module.attr("ResourceManager").attr("instance")();
        py::object asset = rm.attr("get_texture_asset")(name);
        if (asset.is_none()) {
            return TextureHandle();
        }
        return TextureHandle(asset);
    } catch (const py::error_already_set&) {
        return TextureHandle();
    }
}

inline TextureHandle TextureHandle::from_file(
    const std::string& path,
    const std::string& name
) {
    try {
        py::object texture_asset_module = py::module_::import("termin.visualization.render.texture_asset");
        py::object TextureAsset = texture_asset_module.attr("TextureAsset");

        py::object asset;
        if (name.empty()) {
            asset = TextureAsset.attr("from_file")(path);
        } else {
            asset = TextureAsset.attr("from_file")(path, py::arg("name") = name);
        }
        return TextureHandle(asset);
    } catch (const py::error_already_set&) {
        return TextureHandle();
    }
}

inline TextureHandle TextureHandle::from_texture_data(
    py::object texture_data,
    const std::string& name
) {
    try {
        py::object texture_asset_module = py::module_::import("termin.visualization.render.texture_asset");
        py::object TextureAsset = texture_asset_module.attr("TextureAsset");

        py::object asset = TextureAsset(
            py::arg("texture_data") = texture_data,
            py::arg("name") = name
        );
        return TextureHandle(asset);
    } catch (const py::error_already_set&) {
        return TextureHandle();
    }
}

inline TextureHandle TextureHandle::deserialize(const py::dict& data) {
    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].cast<std::string>();
            py::object rm_module = py::module_::import("termin.assets.resources");
            py::object rm = rm_module.attr("ResourceManager").attr("instance")();
            py::object asset = rm.attr("get_texture_asset_by_uuid")(uuid);
            if (!asset.is_none()) {
                return TextureHandle(asset);
            }
        } catch (const py::error_already_set&) {}
    }

    std::string type = data.contains("type") ? data["type"].cast<std::string>() : "none";

    if (type == "named") {
        std::string name = data["name"].cast<std::string>();
        return from_name(name);
    } else if (type == "path") {
        try {
            std::string path = data["path"].cast<std::string>();
            size_t last_slash = path.find_last_of("/\\");
            std::string filename = (last_slash != std::string::npos)
                ? path.substr(last_slash + 1) : path;
            size_t last_dot = filename.find_last_of('.');
            std::string name = (last_dot != std::string::npos)
                ? filename.substr(0, last_dot) : filename;
            return from_name(name);
        } catch (const py::error_already_set&) {
            return TextureHandle();
        }
    }

    return TextureHandle();
}

inline void TextureHandle::deserialize_from(const nos::trent& data) {
    if (!data.is_dict()) {
        asset = py::none();
        return;
    }

    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].as_string();
            py::object rm_module = py::module_::import("termin.assets.resources");
            py::object rm = rm_module.attr("ResourceManager").attr("instance")();
            py::object found = rm.attr("get_texture_asset_by_uuid")(uuid);
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
        asset = py::none();
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
        py::object rm_module = py::module_::import("termin.assets.resources");
        py::object rm = rm_module.attr("ResourceManager").attr("instance")();
        py::object asset = rm.attr("get_material_asset")(name);
        if (asset.is_none()) {
            return MaterialHandle();
        }
        return MaterialHandle(asset);
    } catch (const py::error_already_set&) {
        return MaterialHandle();
    }
}

inline MaterialHandle MaterialHandle::deserialize(const py::dict& data) {
    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].cast<std::string>();
            py::object rm_module = py::module_::import("termin.assets.resources");
            py::object rm = rm_module.attr("ResourceManager").attr("instance")();
            py::object asset = rm.attr("get_material_asset_by_uuid")(uuid);
            if (!asset.is_none()) {
                return MaterialHandle(asset);
            }
        } catch (const py::error_already_set&) {}
    }

    std::string type = data.contains("type") ? data["type"].cast<std::string>() : "none";

    if (type == "named") {
        std::string name = data["name"].cast<std::string>();
        return from_name(name);
    } else if (type == "path") {
        try {
            std::string path = data["path"].cast<std::string>();
            size_t last_slash = path.find_last_of("/\\");
            std::string filename = (last_slash != std::string::npos)
                ? path.substr(last_slash + 1) : path;
            size_t last_dot = filename.find_last_of('.');
            std::string name = (last_dot != std::string::npos)
                ? filename.substr(0, last_dot) : filename;
            return from_name(name);
        } catch (const py::error_already_set&) {
            return MaterialHandle();
        }
    }

    return MaterialHandle();
}

inline void MaterialHandle::deserialize_from(const nos::trent& data) {
    _direct = nullptr;

    if (!data.is_dict()) {
        asset = py::none();
        return;
    }

    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].as_string();
            py::object rm_module = py::module_::import("termin.assets.resources");
            py::object rm = rm_module.attr("ResourceManager").attr("instance")();
            py::object found = rm.attr("get_material_asset_by_uuid")(uuid);
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
        asset = py::none();
    }
}

// ========== SkeletonHandle inline implementations ==========

inline SkeletonHandle SkeletonHandle::from_name(const std::string& name) {
    try {
        py::object rm_module = py::module_::import("termin.assets.resources");
        py::object rm = rm_module.attr("ResourceManager").attr("instance")();
        py::object asset = rm.attr("get_skeleton_asset")(name);
        if (asset.is_none()) {
            return SkeletonHandle();
        }
        return SkeletonHandle(asset);
    } catch (const py::error_already_set&) {
        return SkeletonHandle();
    }
}

inline SkeletonData* SkeletonHandle::get() const {
    if (asset.is_none()) return nullptr;
    py::object res = asset.attr("resource");
    if (res.is_none()) return nullptr;
    return res.cast<SkeletonData*>();
}

inline SkeletonHandle SkeletonHandle::deserialize(const py::dict& data) {
    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].cast<std::string>();
            py::object rm_module = py::module_::import("termin.assets.resources");
            py::object rm = rm_module.attr("ResourceManager").attr("instance")();
            py::object asset = rm.attr("get_skeleton_asset_by_uuid")(uuid);
            if (!asset.is_none()) {
                return SkeletonHandle(asset);
            }
        } catch (const py::error_already_set&) {}
    }

    std::string type = data.contains("type") ? data["type"].cast<std::string>() : "none";

    if (type == "named") {
        std::string name = data["name"].cast<std::string>();
        return from_name(name);
    } else if (type == "path") {
        try {
            std::string path = data["path"].cast<std::string>();
            size_t last_slash = path.find_last_of("/\\");
            std::string filename = (last_slash != std::string::npos)
                ? path.substr(last_slash + 1) : path;
            size_t last_dot = filename.find_last_of('.');
            std::string name = (last_dot != std::string::npos)
                ? filename.substr(0, last_dot) : filename;
            return from_name(name);
        } catch (const py::error_already_set&) {
            return SkeletonHandle();
        }
    }

    return SkeletonHandle();
}

inline void SkeletonHandle::deserialize_from(const nos::trent& data) {
    if (!data.is_dict()) {
        asset = py::none();
        return;
    }

    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].as_string();
            py::object rm_module = py::module_::import("termin.assets.resources");
            py::object rm = rm_module.attr("ResourceManager").attr("instance")();
            py::object found = rm.attr("get_skeleton_asset_by_uuid")(uuid);
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
        asset = py::none();
    }
}

// ========== get_white_texture_handle ==========

inline TextureHandle get_white_texture_handle() {
    // Use Python singleton instead of C++ static to ensure consistency across modules
    try {
        py::object texture_handle_module = py::module_::import("termin.visualization.core.texture_handle");
        py::object handle = texture_handle_module.attr("get_white_texture_handle")();
        return handle.cast<TextureHandle>();
    } catch (const py::error_already_set&) {
        return TextureHandle();
    }
}

// ========== AnimationClipHandle inline implementations ==========

inline AnimationClipHandle AnimationClipHandle::from_name(const std::string& name) {
    try {
        py::object rm_module = py::module_::import("termin.assets.resources");
        py::object rm = rm_module.attr("ResourceManager").attr("instance")();
        py::object asset = rm.attr("get_animation_clip_asset")(name);
        if (asset.is_none()) {
            return AnimationClipHandle();
        }
        return AnimationClipHandle(asset);
    } catch (const py::error_already_set&) {
        return AnimationClipHandle();
    }
}

inline AnimationClipHandle AnimationClipHandle::from_uuid(const std::string& uuid) {
    try {
        py::object rm_module = py::module_::import("termin.assets.resources");
        py::object rm = rm_module.attr("ResourceManager").attr("instance")();
        py::object asset = rm.attr("get_animation_clip_asset_by_uuid")(uuid);
        if (asset.is_none()) {
            return AnimationClipHandle();
        }
        return AnimationClipHandle(asset);
    } catch (const py::error_already_set&) {
        return AnimationClipHandle();
    }
}

inline animation::AnimationClip* AnimationClipHandle::get() const {
    if (asset.is_none()) return nullptr;
    py::object res = asset.attr("resource");
    if (res.is_none()) return nullptr;
    return res.cast<animation::AnimationClip*>();
}

inline AnimationClipHandle AnimationClipHandle::deserialize(const py::dict& data) {
    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].cast<std::string>();
            py::object rm_module = py::module_::import("termin.assets.resources");
            py::object rm = rm_module.attr("ResourceManager").attr("instance")();
            py::object asset = rm.attr("get_animation_clip_asset_by_uuid")(uuid);
            if (!asset.is_none()) {
                return AnimationClipHandle(asset);
            }
        } catch (const py::error_already_set&) {}
    }

    std::string type = data.contains("type") ? data["type"].cast<std::string>() : "none";

    if (type == "named") {
        std::string name = data["name"].cast<std::string>();
        return from_name(name);
    } else if (type == "path") {
        try {
            std::string path = data["path"].cast<std::string>();
            size_t last_slash = path.find_last_of("/\\");
            std::string filename = (last_slash != std::string::npos)
                ? path.substr(last_slash + 1) : path;
            size_t last_dot = filename.find_last_of('.');
            std::string name = (last_dot != std::string::npos)
                ? filename.substr(0, last_dot) : filename;
            return from_name(name);
        } catch (const py::error_already_set&) {
            return AnimationClipHandle();
        }
    }

    return AnimationClipHandle();
}

inline void AnimationClipHandle::deserialize_from(const nos::trent& data) {
    if (!data.is_dict()) {
        asset = py::none();
        return;
    }

    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].as_string();
            py::object rm_module = py::module_::import("termin.assets.resources");
            py::object rm = rm_module.attr("ResourceManager").attr("instance")();
            py::object found = rm.attr("get_animation_clip_asset_by_uuid")(uuid);
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
        asset = py::none();
    }
}

} // namespace termin
