#include "tgfx2/webgpu/webgpu_binding_layout.hpp"

#include <limits>

#include <tcbase/trent/json.h>

namespace tgfx::webgpu {
    namespace {

        const nos::trent* field(const nos::trent& object, const char* name) {
            return object.is_dict() ? object._get(name) : nullptr;
        }

        bool uint_field(const nos::trent& object, const char* name, uint32_t& value) {
            const nos::trent* item = field(object, name);
            if (!item || !item->is_numer())
                return false;
            const int64_t integer = item->as_integer();
            if (integer < 0 || integer > std::numeric_limits<uint32_t>::max())
                return false;
            value = static_cast<uint32_t>(integer);
            return true;
        }

        bool string_field(const nos::trent& object, const char* name, std::string& value) {
            const nos::trent* item = field(object, name);
            if (!item || !item->is_string())
                return false;
            value = item->as_string();
            return true;
        }

        bool bool_field(const nos::trent& object, const char* name, bool& value) {
            const nos::trent* item = field(object, name);
            if (!item || !item->is_bool())
                return false;
            value = item->as_bool();
            return true;
        }

        ShaderResourceKind resource_kind(std::string_view value) {
            if (value == "constant_buffer")
                return ShaderResourceKind::ConstantBuffer;
            if (value == "texture")
                return ShaderResourceKind::Texture;
            if (value == "sampler")
                return ShaderResourceKind::Sampler;
            if (value == "storage_buffer")
                return ShaderResourceKind::StorageBuffer;
            if (value == "storage_texture")
                return ShaderResourceKind::StorageTexture;
            return ShaderResourceKind::None;
        }

        TextureSampleType sample_type(std::string_view value) {
            if (value == "float")
                return TextureSampleType::Float;
            if (value == "unfilterable_float")
                return TextureSampleType::UnfilterableFloat;
            if (value == "depth")
                return TextureSampleType::Depth;
            if (value == "sint")
                return TextureSampleType::Sint;
            if (value == "uint")
                return TextureSampleType::Uint;
            return TextureSampleType::Undefined;
        }

        ResourceAccess resource_access(std::string_view value) {
            if (value == "read_only")
                return ResourceAccess::ReadOnly;
            if (value == "write_only")
                return ResourceAccess::WriteOnly;
            if (value == "read_write")
                return ResourceAccess::ReadWrite;
            return ResourceAccess::Undefined;
        }

        SamplerKind sampler_kind(std::string_view value) {
            if (value == "none")
                return SamplerKind::None;
            if (value == "filtering")
                return SamplerKind::Filtering;
            if (value == "non_filtering")
                return SamplerKind::NonFiltering;
            if (value == "comparison")
                return SamplerKind::Comparison;
            return SamplerKind::None;
        }

        TextureViewAspect view_aspect(std::string_view value) {
            if (value == "all")
                return TextureViewAspect::All;
            if (value == "depth_only")
                return TextureViewAspect::DepthOnly;
            if (value == "stencil_only")
                return TextureViewAspect::StencilOnly;
            return TextureViewAspect::Undefined;
        }

        TextureViewDimension view_dimension(std::string_view value) {
            if (value == "1d")
                return TextureViewDimension::e1D;
            if (value == "2d")
                return TextureViewDimension::e2D;
            if (value == "2d_array")
                return TextureViewDimension::e2DArray;
            if (value == "cube")
                return TextureViewDimension::Cube;
            if (value == "cube_array")
                return TextureViewDimension::CubeArray;
            if (value == "3d")
                return TextureViewDimension::e3D;
            return TextureViewDimension::Undefined;
        }

        BindingLayoutParseResult malformed(std::string_view debug_name, std::string message) {
            return {{}, "shader '" + std::string(debug_name) + "' " + std::move(message)};
        }

    } // namespace

    BindingLayoutParseResult parse_binding_layout(std::string_view json, std::string_view debug_name) {
        if (json.empty())
            return {};
        nos::trent root;
        try {
            root = nos::json::parse(std::string(json));
        } catch (const std::exception& error) {
            return malformed(debug_name, "has invalid layout sidecar: " + std::string(error.what()));
        }

        uint32_t version = 0;
        std::string target;
        if (!uint_field(root, "version", version) || version != 3 || !string_field(root, "target", target) ||
            target != "webgpu") {
            return malformed(debug_name, "requires a WebGPU resource layout sidecar version 3");
        }
        const nos::trent* resources = field(root, "resources");
        if (!resources || !resources->is_list())
            return malformed(debug_name, "layout has no resources array");

        BindingLayoutParseResult result;
        for (const nos::trent& item : resources->as_list()) {
            LayoutEntry entry;
            std::string kind_name;
            const nos::trent* placement = field(item, "webgpu");
            uint32_t group = 0;
            if (!string_field(item, "name", entry.name) || !string_field(item, "kind", kind_name) ||
                !uint_field(item, "stage_mask", entry.stage_mask) || !placement || !placement->is_dict() ||
                !uint_field(*placement, "group", group) || group != 0 ||
                !uint_field(*placement, "binding", entry.binding)) {
                return malformed(debug_name, "has malformed WebGPU placement");
            }
            entry.kind = resource_kind(kind_name);
            if (entry.kind == ShaderResourceKind::None || entry.stage_mask == 0)
                return malformed(debug_name, "has unsupported layout resource kind");

            uint_field(item, "size", entry.size);
            entry.has_sampler_binding = uint_field(*placement, "sampler_binding", entry.sampler_binding);
            if (entry.has_sampler_binding &&
                (entry.kind != ShaderResourceKind::Texture || entry.sampler_binding == entry.binding)) {
                return malformed(debug_name, "has invalid sampler_binding");
            }

            std::string value;
            if (entry.kind == ShaderResourceKind::Texture) {
                if (!string_field(*placement, "sample_type", value) ||
                    (entry.sample_type = sample_type(value)) == TextureSampleType::Undefined ||
                    !string_field(*placement, "view_aspect", value) ||
                    (entry.view_aspect = view_aspect(value)) == TextureViewAspect::Undefined ||
                    !string_field(*placement, "view_dimension", value) ||
                    (entry.view_dimension = view_dimension(value)) == TextureViewDimension::Undefined ||
                    !bool_field(*placement, "multisampled", entry.multisampled) ||
                    !string_field(*placement, "sampler_kind", value)) {
                    return malformed(debug_name, "has incomplete sampled-texture layout metadata");
                }
                entry.sampler_kind = sampler_kind(value);
                const bool valid_sampler =
                    entry.has_sampler_binding ? entry.sampler_kind != SamplerKind::None : value == "none";
                if (!valid_sampler)
                    return malformed(debug_name, "has inconsistent sampled-texture sampler metadata");
            } else if (entry.kind == ShaderResourceKind::Sampler) {
                if (!string_field(*placement, "sampler_kind", value) ||
                    (entry.sampler_kind = sampler_kind(value)) == SamplerKind::None) {
                    return malformed(debug_name, "has invalid sampler metadata");
                }
            } else if (entry.kind == ShaderResourceKind::StorageBuffer) {
                if (!string_field(*placement, "access", value) ||
                    (entry.access = resource_access(value)) == ResourceAccess::Undefined) {
                    return malformed(debug_name, "has invalid storage-buffer access metadata");
                }
            } else if (entry.kind == ShaderResourceKind::StorageTexture) {
                if (!string_field(*placement, "access", value) ||
                    (entry.access = resource_access(value)) == ResourceAccess::Undefined ||
                    !string_field(*placement, "view_aspect", value) ||
                    (entry.view_aspect = view_aspect(value)) == TextureViewAspect::Undefined ||
                    !string_field(*placement, "view_dimension", value) ||
                    (entry.view_dimension = view_dimension(value)) == TextureViewDimension::Undefined ||
                    !bool_field(*placement, "multisampled", entry.multisampled)) {
                    return malformed(debug_name, "has incomplete storage-texture layout metadata");
                }
            }
            result.entries.push_back(std::move(entry));
        }
        return result;
    }

} // namespace tgfx::webgpu
