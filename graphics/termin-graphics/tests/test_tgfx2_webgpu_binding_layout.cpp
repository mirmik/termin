#include "guard_main.h"

#include <string_view>

#include "tgfx2/webgpu/webgpu_binding_layout.hpp"

TEST_CASE("WebGPU layout parser preserves reflected binding semantics") {
    constexpr std::string_view layout = R"json({
      "version": 3,
      "target": "webgpu",
      "resources": [
        {
          "name": "shadow_map", "kind": "texture", "stage_mask": 2,
          "webgpu": {"group": 0, "binding": 0, "sampler_binding": 1,
            "sample_type": "depth", "sampler_kind": "comparison",
            "view_aspect": "depth_only", "view_dimension": "2d", "multisampled": false}
        },
        {
          "name": "values", "kind": "texture", "stage_mask": 2,
          "webgpu": {"group": 0, "binding": 2,
            "sample_type": "unfilterable_float", "sampler_kind": "none",
            "view_aspect": "all", "view_dimension": "2d", "multisampled": false}
        },
        {
          "name": "vertices", "kind": "storage_buffer", "stage_mask": 1,
          "webgpu": {"group": 0, "binding": 3, "access": "read_only"}
        },
        {
          "name": "color", "kind": "texture", "stage_mask": 2,
          "webgpu": {"group": 0, "binding": 4, "sampler_binding": 5,
            "sample_type": "float", "sampler_kind": "filtering",
            "view_aspect": "all", "view_dimension": "2d", "multisampled": false}
        }
      ]
    })json";

    tgfx::webgpu::BindingLayoutParseResult result = tgfx::webgpu::parse_binding_layout(layout, "fixture");
    REQUIRE(result);
    REQUIRE(result.entries.size() == 4);

    const tgfx::webgpu::LayoutEntry& depth = result.entries[0];
    CHECK(depth.sample_type == tgfx::webgpu::TextureSampleType::Depth);
    CHECK(depth.sampler_kind == tgfx::webgpu::SamplerKind::Comparison);
    CHECK(depth.view_aspect == tgfx::webgpu::TextureViewAspect::DepthOnly);
    CHECK(depth.view_dimension == tgfx::webgpu::TextureViewDimension::e2D);
    CHECK(!depth.multisampled);

    const tgfx::webgpu::LayoutEntry& load = result.entries[1];
    CHECK(load.sample_type == tgfx::webgpu::TextureSampleType::UnfilterableFloat);
    CHECK(load.sampler_kind == tgfx::webgpu::SamplerKind::None);
    CHECK(!load.has_sampler_binding);

    const tgfx::webgpu::LayoutEntry& storage = result.entries[2];
    CHECK(storage.kind == tgfx::ShaderResourceKind::StorageBuffer);
    CHECK(storage.access == tgfx::webgpu::ResourceAccess::ReadOnly);
    CHECK(storage.stage_mask == 1);

    const tgfx::webgpu::LayoutEntry& color = result.entries[3];
    CHECK(color.sample_type == tgfx::webgpu::TextureSampleType::Float);
    CHECK(color.sampler_kind == tgfx::webgpu::SamplerKind::Filtering);
}

TEST_CASE("WebGPU layout parser rejects texture bindings without canonical type metadata") {
    constexpr std::string_view layout = R"json({
      "version": 3,
      "target": "webgpu",
      "resources": [{
        "name": "legacy_texture", "kind": "texture", "stage_mask": 2,
        "webgpu": {"group": 0, "binding": 0, "sampler_binding": 1}
      }]
    })json";

    const tgfx::webgpu::BindingLayoutParseResult result = tgfx::webgpu::parse_binding_layout(layout, "legacy-fixture");
    CHECK(!result);
    CHECK(result.error.find("incomplete sampled-texture layout metadata") != std::string::npos);
}
