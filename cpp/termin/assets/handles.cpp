#include "handles.hpp"

#include <optional>

#include "termin/render/texture_gpu.hpp"
#include "termin/assets/texture_data.hpp"
#include "termin/render/material.hpp"

namespace termin {

MeshHandle MeshHandle::from_name(const std::string& name) {
    try {
        // Import ResourceManager and get mesh asset by name
        py::object rm_module = py::module_::import("termin.assets.resources");
        py::object rm = rm_module.attr("ResourceManager").attr("instance")();
        py::object asset = rm.attr("get_mesh_asset")(name);
        if (asset.is_none()) {
            return MeshHandle();
        }
        return MeshHandle(asset);
    } catch (const py::error_already_set&) {
        return MeshHandle();
    }
}

MeshHandle MeshHandle::from_mesh3(
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
    } catch (const py::error_already_set&) {
        return MeshHandle();
    }
}

MeshHandle MeshHandle::from_vertices_indices(
    py::array_t<float> vertices,
    py::array_t<uint32_t> indices,
    const std::string& name
) {
    try {
        py::object mesh_module = py::module_::import("termin.mesh.mesh");
        py::object Mesh3 = mesh_module.attr("Mesh3");
        py::object mesh = Mesh3(
            py::arg("vertices") = vertices,
            py::arg("triangles") = indices
        );
        return from_mesh3(mesh, name);
    } catch (const py::error_already_set&) {
        return MeshHandle();
    }
}

MeshHandle MeshHandle::deserialize(const py::dict& data) {
    // UUID-based lookup (primary format in scene files)
    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].cast<std::string>();
            py::object rm_module = py::module_::import("termin.assets.resources");
            py::object rm = rm_module.attr("ResourceManager").attr("instance")();
            py::object handle = rm.attr("get_mesh_by_uuid")(uuid);
            if (!handle.is_none()) {
                return handle.cast<MeshHandle>();
            }
        } catch (const py::error_already_set&) {
            // Fall through to other methods
        }
    }

    std::string type = data.contains("type") ? data["type"].cast<std::string>() : "none";

    if (type == "named") {
        std::string name = data["name"].cast<std::string>();
        return from_name(name);
    } else if (type == "path") {
        try {
            std::string path = data["path"].cast<std::string>();
            py::object mesh_asset_module = py::module_::import("termin.visualization.core.mesh_asset");
            py::object asset = mesh_asset_module.attr("MeshAsset")(
                py::none(),  // mesh_data
                py::arg("source_path") = path
            );
            return MeshHandle(asset);
        } catch (const py::error_already_set&) {
            return MeshHandle();
        }
    }

    return MeshHandle();
}

TextureHandle TextureHandle::from_name(const std::string& name) {
    try {
        // Import ResourceManager and get texture asset by name
        py::object rm_module = py::module_::import("termin.assets.resources");
        py::object rm = rm_module.attr("ResourceManager").attr("instance")();
        py::object asset = rm.attr("get_texture_asset")(name);
        if (asset.is_none()) {
            return TextureHandle();
        }
        return TextureHandle(asset);
    } catch (const py::error_already_set& e) {
        // Python error - return empty handle
        return TextureHandle();
    }
}

TextureHandle TextureHandle::from_file(
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

TextureHandle TextureHandle::from_texture_data(
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

TextureHandle TextureHandle::deserialize(const py::dict& data) {
    std::string type = data.contains("type") ? data["type"].cast<std::string>() : "none";

    if (type == "named") {
        std::string name = data["name"].cast<std::string>();
        return from_name(name);
    } else if (type == "path") {
        try {
            std::string path = data["path"].cast<std::string>();
            py::object texture_asset_module = py::module_::import("termin.visualization.render.texture_asset");
            py::object asset = texture_asset_module.attr("TextureAsset").attr("from_file")(path);
            return TextureHandle(asset);
        } catch (const py::error_already_set&) {
            return TextureHandle();
        }
    }

    return TextureHandle();
}

void TextureHandle::bind(GraphicsBackend* graphics, int unit, int64_t context_key) const {
    TextureGPU* gpu_ptr = gpu();
    TextureData* data = get();
    if (gpu_ptr == nullptr || data == nullptr) {
        return;
    }
    gpu_ptr->bind(graphics, *data, version(), unit, context_key);
}

// Singleton for white texture
static std::optional<TextureHandle> g_white_texture_handle;

TextureHandle get_white_texture_handle() {
    if (!g_white_texture_handle.has_value()) {
        try {
            py::object texture_asset_module = py::module_::import("termin.visualization.render.texture_asset");
            py::object TextureAsset = texture_asset_module.attr("TextureAsset");
            py::object asset = TextureAsset.attr("white_1x1")();
            g_white_texture_handle = TextureHandle(asset);
        } catch (const py::error_already_set&) {
            g_white_texture_handle = TextureHandle();
        }
    }
    return g_white_texture_handle.value();
}

// ===== MaterialHandle =====

std::string MaterialHandle::name() const {
    if (_direct != nullptr) {
        return _direct->name;
    }
    if (asset.is_none()) return "";
    return asset.attr("name").cast<std::string>();
}

Material* MaterialHandle::get() const {
    if (_direct != nullptr) {
        return _direct;
    }
    if (asset.is_none()) return nullptr;
    // asset.resource is the Material
    py::object res = asset.attr("resource");
    if (res.is_none()) return nullptr;
    return res.cast<Material*>();
}

MaterialHandle MaterialHandle::from_name(const std::string& name) {
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

Material* MaterialHandle::get_material() const {
    Material* mat = get();
    if (mat != nullptr) {
        return mat;
    }
    // Return error material if not available
    try {
        py::object mat_module = py::module_::import("termin.visualization.core.material");
        py::object error_mat = mat_module.attr("get_error_material")();
        return error_mat.cast<Material*>();
    } catch (const py::error_already_set&) {
        return nullptr;
    }
}

py::dict MaterialHandle::serialize() const {
    if (_direct != nullptr) {
        // Direct material - check if has source_path
        if (!_direct->source_path.empty()) {
            py::dict d;
            d["type"] = "path";
            d["path"] = _direct->source_path;
            return d;
        }
        py::dict d;
        d["type"] = "direct_unsupported";
        return d;
    }
    if (asset.is_none()) {
        py::dict d;
        d["type"] = "none";
        return d;
    }
    py::object source_path = asset.attr("source_path");
    if (!source_path.is_none()) {
        py::dict d;
        d["type"] = "path";
        d["path"] = py::str(source_path.attr("as_posix")());
        return d;
    }
    py::dict d;
    d["type"] = "named";
    d["name"] = asset.attr("name");
    return d;
}

MaterialHandle MaterialHandle::deserialize(const py::dict& data) {
    // UUID-based lookup (primary format in scene files)
    if (data.contains("uuid")) {
        try {
            std::string uuid = data["uuid"].cast<std::string>();
            py::object rm_module = py::module_::import("termin.assets.resources");
            py::object rm = rm_module.attr("ResourceManager").attr("instance")();
            py::object asset = rm.attr("get_material_asset_by_uuid")(uuid);
            if (!asset.is_none()) {
                return MaterialHandle(asset);
            }
        } catch (const py::error_already_set&) {
            // Fall through to other methods
        }
    }

    std::string type = data.contains("type") ? data["type"].cast<std::string>() : "none";

    if (type == "named") {
        std::string name = data["name"].cast<std::string>();
        return from_name(name);
    } else if (type == "path") {
        try {
            std::string path = data["path"].cast<std::string>();
            py::object material_asset_module = py::module_::import("termin.visualization.core.material_asset");
            py::object asset = material_asset_module.attr("MaterialAsset").attr("from_file")(path);
            return MaterialHandle(asset);
        } catch (const py::error_already_set&) {
            return MaterialHandle();
        }
    }

    return MaterialHandle();
}

} // namespace termin
