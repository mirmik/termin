#include "guard_main.h"

GUARD_TEST_MAIN();

#include <cstring>
#include <vector>

#include <components/mesh_component.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/render/line_renderer.hpp>
#include <termin/render/material_pipeline.hpp>
#include <termin/render/render_item_submission.hpp>
#include <termin/render/world_text_component.hpp>
#include <termin/tc_scene.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

extern "C" {
#include <core/tc_drawable_protocol.h>
#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx/resources/tc_shader_registry.h>
}

namespace {

constexpr const char* kVertexSource = R"(
struct VertexOutput { float4 position : SV_Position; };

[shader("vertex")]
VertexOutput vs_main() {
    VertexOutput output;
    output.position = float4(0.0, 0.0, 0.0, 1.0);
    return output;
}
)";

constexpr const char* kFragmentSource = R"(
struct FragmentInput
{
    float4 screen_pos : SV_Position;
    float3 world_pos : TEXCOORD0;
    float3 normal_world : TEXCOORD1;
};

struct FragmentOutput { float4 color : SV_Target0; };

[shader("fragment")]
FragmentOutput fs_main(FragmentInput input)
{
    FragmentOutput output;
    output.color = float4(abs(input.normal_world), 1.0);
    return output;
}
)";

termin::TcShader make_test_material_shader(const char* uuid)
{
    const tc_shader_create_desc shader_desc = {
        {
            kVertexSource,
            kFragmentSource,
            nullptr,
            "LineRendererContractMaterial",
            nullptr,
            "vs_main",
            "fs_main",
            nullptr
        },
        uuid,
        TC_SHADER_LANGUAGE_SLANG,
        TC_SHADER_ARTIFACT_OPTIONAL
    };
    tc_shader_handle handle = tc_shader_from_sources_desc(&shader_desc);
    return termin::TcShader(handle);
}

termin::MaterialPipelinePassContract line_material_fragment_contract()
{
    termin::MaterialPipelinePassContract contract;
    contract.debug_name = "custom_line_material_fragment";
    contract.required_material_fragment_input =
        termin::material_pipeline_standard_material_fragment_interface();
    contract.uses_material_fragment = true;
    return contract;
}

termin::MaterialPipelinePassContract line_auxiliary_contract()
{
    termin::MaterialPipelinePassContract contract;
    contract.debug_name = "custom_line_auxiliary";
    contract.required_material_fragment_input = termin::MaterialFragmentInterface{};
    contract.uses_material_fragment = true;
    return contract;
}

bool has_variant(
    const std::vector<termin::TcShader>& shaders,
    tc_shader_variant_op variant_op)
{
    for (const termin::TcShader& shader : shaders) {
        if (shader.variant_op() == variant_op) {
            return true;
        }
    }
    return false;
}

termin::TcMesh make_two_submesh_mesh()
{
    const float vertices[] = {
        0.0f, 0.0f, 0.0f,
        1.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f,
        2.0f, 0.0f, 0.0f,
        3.0f, 0.0f, 0.0f,
        2.0f, 1.0f, 0.0f,
    };
    const uint32_t indices[] = {0, 1, 2, 3, 4, 5};
    auto make_submesh = [](uint32_t first_index, uint32_t index_count, uint32_t material_slot, const char* name) {
        tc_submesh submesh{};
        submesh.first_index = first_index;
        submesh.index_count = index_count;
        submesh.material_slot = material_slot;
        submesh.draw_mode = TC_DRAW_TRIANGLES;
        std::strncpy(submesh.name, name, TC_SUBMESH_NAME_MAX - 1);
        return submesh;
    };
    const std::vector<tc_submesh> submeshes = {
        make_submesh(0, 3, 0, "left"),
        make_submesh(3, 3, 1, "right"),
    };
    tc_vertex_layout layout = tc_vertex_layout_pos();
    termin::TcMeshCreateInfo create_info;
    create_info.data = termin::TcMeshInterleavedDataView{
        vertices,
        6,
        indices,
        6,
        &layout};
    create_info.submeshes = submeshes.data();
    create_info.submesh_count = submeshes.size();
    create_info.name = "mesh-renderer-geometry-ids-test";
    create_info.uuid_hint = "mesh-renderer-geometry-ids-test";
    return termin::TcMesh::from_interleaved(create_info);
}

} // namespace

TEST_CASE("LineRenderer context-aware usage collection follows explicit pass contract") {
    tc_shader_init();

    termin::TcShader material_shader = make_test_material_shader(
        "line-contract-material");
    REQUIRE(material_shader.is_valid());

    termin::LineRenderer renderer;
    renderer.render_mode = termin::LineRenderMode::WorldTube;
    renderer.cast_shadow = true;

    termin::ShaderOverrideContext context;
    context.phase_mark = "actor_attribute";
    context.geometry_id = 0;
    context.original_shader = material_shader;
    context.pass_contract = line_material_fragment_contract();

    std::vector<termin::TcShader> emitted;
    renderer.collect_shader_usages_with_context(
        context,
        [&](termin::TcShader shader) {
            emitted.push_back(shader);
        });

    CHECK(emitted.size() >= 3u);
    CHECK(has_variant(emitted, TC_SHADER_VARIANT_LINE_TUBE_BODY));
    CHECK(has_variant(emitted, TC_SHADER_VARIANT_LINE_TUBE_CAP));

    termin::ShaderOverrideContext auxiliary_context;
    auxiliary_context.phase_mark = "actor_attribute";
    auxiliary_context.geometry_id = 0;
    auxiliary_context.original_shader = material_shader;
    auxiliary_context.pass_contract = line_auxiliary_contract();

    std::vector<termin::TcShader> auxiliary_emitted;
    renderer.collect_shader_usages_with_context(
        auxiliary_context,
        [&](termin::TcShader shader) {
            auxiliary_emitted.push_back(shader);
        });

    CHECK(!has_variant(auxiliary_emitted, TC_SHADER_VARIANT_LINE_TUBE_BODY));
    CHECK(!has_variant(auxiliary_emitted, TC_SHADER_VARIANT_LINE_TUBE_CAP));

    termin::ShaderOverrideContext material_context;
    material_context.phase_mark = "shadow";
    material_context.geometry_id = 0;
    material_context.original_shader = material_shader;
    material_context.pass_contract = line_material_fragment_contract();

    std::vector<termin::TcShader> material_emitted;
    renderer.collect_shader_usages_with_context(
        material_context,
        [&](termin::TcShader shader) {
            material_emitted.push_back(shader);
        });

    CHECK(has_variant(material_emitted, TC_SHADER_VARIANT_LINE_TUBE_BODY));
    CHECK(has_variant(material_emitted, TC_SHADER_VARIANT_LINE_TUBE_CAP));

    tc_shader_shutdown();
}

TEST_CASE("MeshRenderer render items are permissive for pass phase labels") {
    tc_material_init();
    tc_mesh_init();

    tc_material_handle material_handle = tc_material_create(
        "mesh-renderer-permissive-material",
        "mesh-renderer-permissive-material");
    REQUIRE(tc_material_is_valid(material_handle));
    tc_material* material = tc_material_get(material_handle);
    REQUIRE(material != nullptr);
    REQUIRE(tc_material_add_phase(
        material,
        tc_shader_handle_invalid(),
        "opaque",
        0) != nullptr);

    termin::TcMesh mesh = make_two_submesh_mesh();
    REQUIRE(mesh.is_valid());

    termin::TcSceneRef scene = termin::TcSceneRef::create("mesh-renderer-geometry-ids");
    termin::Entity entity = scene.create_entity("mesh");

    auto* mesh_component = new termin::MeshComponent();
    mesh_component->set_mesh(mesh);
    entity.add_component(mesh_component);

    auto* renderer = new termin::MeshRenderer();
    renderer->set_material(termin::TcMaterial(material_handle));
    renderer->set_material_slot(1, termin::TcMaterial(material_handle));
    entity.add_component(renderer);

    tc_render_item_collect_context collect_context{};
    collect_context.phase_mark = "custom_depth";
    collect_context.flags = TC_RENDER_ITEM_COLLECT_FLAG_ALLOW_MISSING_MATERIAL_PHASE;
    collect_context.debug_pass_name = "test";

    termin::RenderItemCollection collection;
    REQUIRE(termin::collect_drawable_render_items(
        renderer->tc_component_ptr(),
        collect_context,
        collection));

    REQUIRE(collection.items.size() == 2u);
    CHECK(collection.items[0].kind == TC_RENDER_ITEM_KIND_MESH);
    CHECK(collection.items[0].geometry_id == 0);
    CHECK(collection.items[1].kind == TC_RENDER_ITEM_KIND_MESH);
    CHECK(collection.items[1].geometry_id == 1);

    tc_mesh_shutdown();
    tc_material_shutdown();
}

TEST_CASE("MeshRenderer emits mesh render items through drawable protocol") {
    tc_material_init();
    tc_mesh_init();

    tc_material_handle material_handle = tc_material_create(
        "mesh-renderer-render-item-material",
        "mesh-renderer-render-item-material");
    REQUIRE(tc_material_is_valid(material_handle));
    tc_material* material = tc_material_get(material_handle);
    REQUIRE(material != nullptr);
    tc_material_phase* phase = tc_material_add_phase(
        material,
        tc_shader_handle_invalid(),
        "opaque",
        11);
    REQUIRE(phase != nullptr);

    termin::TcMesh mesh = make_two_submesh_mesh();
    REQUIRE(mesh.is_valid());

    termin::TcSceneRef scene = termin::TcSceneRef::create("mesh-renderer-render-items");
    termin::Entity entity = scene.create_entity("mesh");

    auto* mesh_component = new termin::MeshComponent();
    mesh_component->set_mesh(mesh);
    entity.add_component(mesh_component);

    auto* renderer = new termin::MeshRenderer();
    renderer->set_material(termin::TcMaterial(material_handle));
    renderer->set_material_slot(1, termin::TcMaterial(material_handle));
    entity.add_component(renderer);

    tc_render_item_collect_context collect_context{};
    collect_context.phase_mark = "opaque";
    collect_context.debug_pass_name = "test";

    termin::RenderItemCollection collection;
    REQUIRE(termin::collect_drawable_render_items(
        renderer->tc_component_ptr(),
        collect_context,
        collection));

    const std::vector<tc_render_item>& items = collection.items;
    REQUIRE(items.size() == 2u);
    CHECK(items[0].kind == TC_RENDER_ITEM_KIND_MESH);
    CHECK(items[0].component == renderer->tc_component_ptr());
    CHECK(items[0].geometry_id == 0);
    CHECK(items[0].material_phase == phase);
    CHECK(items[0].payload.mesh.mesh == mesh.get());
    CHECK(items[0].payload.mesh.submesh_index == 0u);
    CHECK((items[0].flags & TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX) != 0u);
    CHECK((items[0].flags & TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE) != 0u);

    CHECK(items[1].kind == TC_RENDER_ITEM_KIND_MESH);
    CHECK(items[1].geometry_id == 1);
    CHECK(items[1].material_phase == phase);
    CHECK(items[1].payload.mesh.mesh == mesh.get());
    CHECK(items[1].payload.mesh.submesh_index == 1u);

    tc_mesh_shutdown();
    tc_material_shutdown();
}

TEST_CASE("MeshRenderer can emit material-phaseless mesh render items for pick passes") {
    tc_material_init();
    tc_mesh_init();

    tc_material_handle material_handle = tc_material_create(
        "mesh-renderer-render-item-opaque-only",
        "mesh-renderer-render-item-opaque-only");
    REQUIRE(tc_material_is_valid(material_handle));
    tc_material* material = tc_material_get(material_handle);
    REQUIRE(material != nullptr);
    REQUIRE(tc_material_add_phase(
        material,
        tc_shader_handle_invalid(),
        "opaque",
        0) != nullptr);

    termin::TcMesh mesh = make_two_submesh_mesh();
    REQUIRE(mesh.is_valid());

    termin::TcSceneRef scene = termin::TcSceneRef::create("mesh-renderer-render-items-pick");
    termin::Entity entity = scene.create_entity("mesh");

    auto* mesh_component = new termin::MeshComponent();
    mesh_component->set_mesh(mesh);
    entity.add_component(mesh_component);

    auto* renderer = new termin::MeshRenderer();
    renderer->set_material(termin::TcMaterial(material_handle));
    renderer->set_material_slot(1, termin::TcMaterial(material_handle));
    entity.add_component(renderer);

    tc_render_item_collect_context collect_context{};
    collect_context.phase_mark = "pick";
    collect_context.flags = TC_RENDER_ITEM_COLLECT_FLAG_ALLOW_MISSING_MATERIAL_PHASE;
    collect_context.debug_pass_name = "IdPass";

    termin::RenderItemCollection collection;
    REQUIRE(termin::collect_drawable_render_items(
        renderer->tc_component_ptr(),
        collect_context,
        collection));

    const std::vector<tc_render_item>& items = collection.items;
    REQUIRE(items.size() == 2u);
    CHECK(items[0].kind == TC_RENDER_ITEM_KIND_MESH);
    CHECK(items[0].material_phase == nullptr);
    CHECK((items[0].flags & TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE) == 0u);
    CHECK(items[1].kind == TC_RENDER_ITEM_KIND_MESH);
    CHECK(items[1].material_phase == nullptr);
    CHECK((items[1].flags & TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE) == 0u);

    tc_mesh_shutdown();
    tc_material_shutdown();
}

TEST_CASE("LineRenderer emits direct modes as line batch render items") {
    tc_material_init();
    tc_shader_init();

    termin::TcSceneRef scene = termin::TcSceneRef::create("line-renderer-render-items");
    termin::Entity entity = scene.create_entity("line");

    auto* renderer = new termin::LineRenderer();
    renderer->set_points({tc_vec3{0, 0, 0}, tc_vec3{1, 0, 0}});
    renderer->set_render_mode(termin::LineRenderMode::WorldBillboard);
    renderer->set_width(0.25f);
    entity.add_component(renderer);

    tc_render_item_collect_context collect_context{};
    collect_context.phase_mark = "opaque";
    collect_context.debug_pass_name = "test";

    termin::RenderItemCollection collection;
    REQUIRE(termin::collect_drawable_render_items(
        renderer->tc_component_ptr(),
        collect_context,
        collection));

    const std::vector<tc_render_item>& items = collection.items;
    REQUIRE(items.size() == 1u);
    CHECK(items[0].kind == TC_RENDER_ITEM_KIND_LINE_BATCH);
    CHECK(items[0].component == renderer->tc_component_ptr());
    CHECK(items[0].geometry_id == 0);
    CHECK(items[0].payload.line_batch.points != nullptr);
    CHECK(items[0].payload.line_batch.point_count == 2u);
    CHECK(items[0].payload.line_batch.width == 0.25f);
    CHECK(items[0].payload.line_batch.render_mode ==
          static_cast<uint32_t>(termin::LineRenderMode::WorldBillboard));
    CHECK((items[0].flags & TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX) != 0u);
    CHECK((items[0].flags & TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE) != 0u);

    const tc_render_item_vec3* collected_points = items[0].payload.line_batch.points;
    renderer->set_points({tc_vec3{5, 0, 0}, tc_vec3{6, 0, 0}});
    REQUIRE(items[0].payload.line_batch.points == collected_points);
    CHECK(items[0].payload.line_batch.points[0].x == 0.0);
    CHECK(items[0].payload.line_batch.points[1].x == 1.0);

    tc_shader_shutdown();
    tc_material_shutdown();
}

TEST_CASE("LineRenderer can emit material-phaseless line render items for pick passes") {
    tc_material_init();
    tc_shader_init();

    termin::LineRenderer::register_type();
    CHECK(termin::render_item_encoder_supports_pass(
        TC_RENDER_ITEM_KIND_LINE_BATCH,
        termin::RenderItemPassSemantic::Id));

    termin::TcSceneRef scene = termin::TcSceneRef::create("line-renderer-render-items-pick");
    termin::Entity entity = scene.create_entity("line");

    auto* renderer = new termin::LineRenderer();
    renderer->set_points({tc_vec3{0, 0, 0}, tc_vec3{1, 0, 0}});
    renderer->set_render_mode(termin::LineRenderMode::WorldBillboard);
    tc_material_handle material_handle = tc_material_create(
        "line-renderer-render-item-pick-opaque-only",
        "line-renderer-render-item-pick-opaque-only");
    REQUIRE(tc_material_is_valid(material_handle));
    tc_material* material = tc_material_get(material_handle);
    REQUIRE(material != nullptr);
    REQUIRE(tc_material_add_phase(
        material,
        tc_shader_handle_invalid(),
        "opaque",
        0) != nullptr);
    renderer->set_material(termin::TcMaterial(material_handle));
    entity.add_component(renderer);

    tc_render_item_collect_context collect_context{};
    collect_context.phase_mark = "pick";
    collect_context.flags = TC_RENDER_ITEM_COLLECT_FLAG_ALLOW_MISSING_MATERIAL_PHASE;
    collect_context.debug_pass_name = "IdPass";

    termin::RenderItemCollection collection;
    REQUIRE(termin::collect_drawable_render_items(
        renderer->tc_component_ptr(),
        collect_context,
        collection));

    const std::vector<tc_render_item>& items = collection.items;
    REQUIRE(items.size() == 1u);
    CHECK(items[0].kind == TC_RENDER_ITEM_KIND_LINE_BATCH);
    CHECK(items[0].material_phase == nullptr);
    CHECK((items[0].flags & TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE) == 0u);
    CHECK((items[0].flags & TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX) != 0u);

    tc_shader_shutdown();
    tc_material_shutdown();
}

TEST_CASE("LineRenderer keeps mesh modes on mesh render item path") {
    tc_material_init();
    tc_shader_init();
    tc_mesh_init();

    termin::TcSceneRef scene = termin::TcSceneRef::create("line-renderer-mesh-render-items");
    termin::Entity entity = scene.create_entity("line");

    auto* renderer = new termin::LineRenderer();
    renderer->set_points({tc_vec3{0, 0, 0}, tc_vec3{1, 0, 0}});
    renderer->set_render_mode(termin::LineRenderMode::WorldMesh);
    tc_material_handle material_handle = tc_material_create(
        "line-renderer-mesh-render-item-material",
        "line-renderer-mesh-render-item-material");
    REQUIRE(tc_material_is_valid(material_handle));
    tc_material* material = tc_material_get(material_handle);
    REQUIRE(material != nullptr);
    REQUIRE(tc_material_add_phase(
        material,
        tc_shader_handle_invalid(),
        "opaque",
        0) != nullptr);
    renderer->set_material(termin::TcMaterial(material_handle));
    entity.add_component(renderer);

    tc_render_item_collect_context collect_context{};
    collect_context.phase_mark = "opaque";
    collect_context.debug_pass_name = "test";

    termin::RenderItemCollection collection;
    REQUIRE(termin::collect_drawable_render_items(
        renderer->tc_component_ptr(),
        collect_context,
        collection));

    const std::vector<tc_render_item>& items = collection.items;
    REQUIRE(items.size() == 1u);
    CHECK(items[0].kind == TC_RENDER_ITEM_KIND_MESH);
    CHECK(items[0].component == renderer->tc_component_ptr());
    CHECK(items[0].payload.mesh.mesh != nullptr);

    tc_mesh_shutdown();
    tc_shader_shutdown();
    tc_material_shutdown();
}

TEST_CASE("WorldTextComponent emits text batch render items with owned text payload") {
    tc_material_init();
    tc_shader_init();

    termin::TcSceneRef scene = termin::TcSceneRef::create("world-text-render-items");
    termin::Entity entity = scene.create_entity("label");

    auto* text = new termin::WorldTextComponent();
    text->set_text("hello");
    text->set_font_path("font-a.ttf");
    text->set_phase_mark("transparent");
    text->set_size(0.75f);
    text->set_anchor(termin::WorldTextAnchor::Right);
    text->set_orientation(termin::WorldTextOrientation::Fixed);
    text->set_local_offset(termin::Vec3{1.0, 2.0, 3.0});
    entity.add_component(text);

    tc_render_item_collect_context collect_context{};
    collect_context.phase_mark = "transparent";
    collect_context.debug_pass_name = "ColorPass";

    termin::RenderItemCollection collection;
    REQUIRE(termin::collect_drawable_render_items(
        text->tc_component_ptr(),
        collect_context,
        collection));

    REQUIRE(collection.items.size() == 1u);
    const tc_render_item& item = collection.items[0];
    CHECK(item.kind == TC_RENDER_ITEM_KIND_TEXT_BATCH);
    CHECK(item.component == text->tc_component_ptr());
    CHECK(item.geometry_id == 0);
    CHECK(item.material_phase != nullptr);
    REQUIRE(item.payload.text_batch.text != nullptr);
    REQUIRE(item.payload.text_batch.font_path != nullptr);
    CHECK(std::strcmp(item.payload.text_batch.text, "hello") == 0);
    CHECK(std::strcmp(item.payload.text_batch.font_path, "font-a.ttf") == 0);
    CHECK(item.payload.text_batch.size == 0.75f);
    CHECK(item.payload.text_batch.anchor ==
          static_cast<uint32_t>(termin::WorldTextAnchor::Right));
    CHECK(item.payload.text_batch.orientation ==
          static_cast<uint32_t>(termin::WorldTextOrientation::Fixed));
    CHECK(item.payload.text_batch.local_offset.x == 1.0);
    CHECK(item.payload.text_batch.local_offset.y == 2.0);
    CHECK(item.payload.text_batch.local_offset.z == 3.0);

    const char* collected_text = item.payload.text_batch.text;
    const char* collected_font_path = item.payload.text_batch.font_path;
    text->set_text("changed");
    text->set_font_path("font-b.ttf");
    REQUIRE(item.payload.text_batch.text == collected_text);
    REQUIRE(item.payload.text_batch.font_path == collected_font_path);
    CHECK(std::strcmp(item.payload.text_batch.text, "hello") == 0);
    CHECK(std::strcmp(item.payload.text_batch.font_path, "font-a.ttf") == 0);

    tc_shader_shutdown();
    tc_material_shutdown();
}
