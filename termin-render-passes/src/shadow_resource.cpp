#include <termin/lighting/shadow.hpp>

#include <termin/render/frame_graph_resource_registry.hpp>

namespace termin {
namespace {

FrameGraphResource* create_shadow_map_array(const ResourceSpec& spec)
{
    const int resolution = spec.size ? spec.size->first : 1024;
    return new ShadowMapArrayResource(resolution);
}

FrameGraphResourceSampledTexture shadow_map_array_sampled_texture(
    const FrameGraphResource& resource)
{
    const auto& shadow_array =
        static_cast<const ShadowMapArrayResource&>(resource);
    if (shadow_array.entries.empty()) {
        return {};
    }
    // The farthest cascade is the most useful single-image overview: it
    // covers the complete configured shadow distance, while the first cascade
    // can legitimately contain no casters in sparse scenes.
    return {
        .texture = shadow_array.entries.back().depth_tex2,
        .kind = FrameGraphResourceSampledTextureKind::Depth,
    };
}

} // namespace

bool register_shadow_map_array_resource_type()
{
    const FrameGraphResourceTypeDescriptor descriptor{
        .resource_type = "shadow_map_array",
        .create = create_shadow_map_array,
        .sampled_texture = shadow_map_array_sampled_texture,
    };
    if (frame_graph_resource_type_matches(descriptor)) {
        return true;
    }
    return register_frame_graph_resource_type(descriptor);
}

} // namespace termin
