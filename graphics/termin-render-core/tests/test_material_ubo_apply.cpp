#include "guard_main.h"

GUARD_TEST_MAIN();

#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include <tcbase/tc_log.h>
#include <termin/render/material_ubo_apply.hpp>
#include <tgfx2/frame_data_cache.hpp>
#include <tgfx2/pipeline_cache.hpp>
#include <tgfx2/render_context.hpp>
#include <termin/render/tgfx2_bridge.hpp>
#include "render_execution_recording_device.hpp"

extern "C" {
#include <tcbase/tc_resource.h>
#include <tgfx/resources/tc_texture_registry.h>
}

namespace {

    std::string captured_log;

    void capture_log(tc_log_level level, const char* message) {
        if (level == TC_LOG_ERROR && message) {
            captured_log = message;
        }
    }

    int32_t read_int_at(const std::array<uint8_t, 16>& buffer, size_t offset) {
        int32_t value = 0;
        std::memcpy(&value, buffer.data() + offset, sizeof(value));
        return value;
    }

    float read_float_at(const std::array<uint8_t, 16>& buffer, size_t offset) {
        float value = 0.0f;
        std::memcpy(&value, buffer.data() + offset, sizeof(value));
        return value;
    }

    tc_uniform_value uniform_int(const char* name, int32_t value) {
        tc_uniform_value uniform{};
        std::snprintf(uniform.name, sizeof(uniform.name), "%s", name);
        uniform.type = TC_UNIFORM_INT;
        uniform.data.i = value;
        return uniform;
    }

    tc_uniform_value uniform_bool(const char* name, bool value) {
        tc_uniform_value uniform{};
        std::snprintf(uniform.name, sizeof(uniform.name), "%s", name);
        uniform.type = TC_UNIFORM_BOOL;
        uniform.data.i = value ? 1 : 0;
        return uniform;
    }

    tc_uniform_value uniform_float(const char* name, float value) {
        tc_uniform_value uniform{};
        std::snprintf(uniform.name, sizeof(uniform.name), "%s", name);
        uniform.type = TC_UNIFORM_FLOAT;
        uniform.data.f = value;
        return uniform;
    }

    tc_uniform_value uniform_color(const char* name, uint8_t type, float r, float g, float b, float a) {
        tc_uniform_value uniform{};
        std::snprintf(uniform.name, sizeof(uniform.name), "%s", name);
        uniform.type = type;
        if (type == TC_UNIFORM_SRGB_COLOR) {
            uniform.data.srgb_color = {r, g, b, a};
        } else if (type == TC_UNIFORM_LINEAR_COLOR) {
            uniform.data.linear_color = {r, g, b, a};
        } else {
            uniform.data.v4[0] = r;
            uniform.data.v4[1] = g;
            uniform.data.v4[2] = b;
            uniform.data.v4[3] = a;
        }
        return uniform;
    }

} // namespace

namespace {
    struct MaterialTextureRegistry {
        MaterialTextureRegistry() { tc_texture_init(); }
        ~MaterialTextureRegistry() {
            tc_resource_clear_loader();
            tc_texture_shutdown();
        }
    };

    class MaterialTextureDevice : public termin::test::ExecutionRecordingDevice {
    public:
        std::vector<tgfx::SamplerDesc> samplers;
        std::vector<std::vector<tgfx::BoundResourceBinding>> bound_sets;
        uint32_t image_uploads = 0;
        uint32_t image_version = 0;
        bool destroy_after_image = false;

        tgfx::SamplerHandle create_sampler(const tgfx::SamplerDesc& desc) override {
            samplers.push_back(desc);
            return tgfx::SamplerHandle{static_cast<uint32_t>(samplers.size())};
        }
        uintptr_t pipeline_resource_layout_token(tgfx::PipelineHandle) const override { return 1; }
        tgfx::ResourceSetHandle create_bound_resource_set(const tgfx::BoundResourceSetDesc& desc) override {
            std::vector<tgfx::BoundResourceBinding> values;
            tgfx::for_each_bound_resource_binding(desc, [&](const auto& binding) {
                values.push_back(binding);
            });
            bound_sets.push_back(std::move(values));
            return tgfx::ResourceSetHandle{static_cast<uint32_t>(bound_sets.size())};
        }
        tgfx::TextureHandle ensure_tc_texture(tc_texture* texture) override {
            const auto handle = tc_texture_find(texture->header.uuid);
            if (!texture->header.is_loaded && !tc_texture_ensure_loaded(handle))
                return {};
            texture = tc_texture_get(handle);
            if (!texture)
                return {};
            if (image_version != texture->header.version) {
                image_version = texture->header.version;
                ++image_uploads;
            }
            if (destroy_after_image)
                tc_texture_destroy(handle);
            return tgfx::TextureHandle{100 + image_uploads};
        }
    };

    struct MaterialTextureLoader {
        tc_texture_handle handle = tc_texture_handle_invalid();
        bool relocated = false;

        static bool load(const char*, void* user) {
            auto& loader = *static_cast<MaterialTextureLoader*>(user);
            const auto old = reinterpret_cast<uintptr_t>(tc_texture_get(loader.handle));
            for (int i = 0; i < 64; ++i)
                tc_texture_create(nullptr);
            tc_texture* texture = tc_texture_get(loader.handle);
            loader.relocated = old != reinterpret_cast<uintptr_t>(texture);
            auto sampler = tc_sampler_desc_default();
            sampler.address_u = TC_SAMPLER_ADDRESS_CLAMP_TO_EDGE;
            sampler.min_filter = TC_SAMPLER_FILTER_NEAREST;
            if (!tc_texture_set_sampler(texture, &sampler))
                return false;
            const uint8_t pixel[] = {255, 255, 255, 255};
            const tc_texture_pixel_data pixels{pixel, sizeof(pixel), 1, 1, 4};
            return tc_texture_set_data(texture, &pixels, nullptr, nullptr);
        }
    };
}

TEST_CASE("material binding passes the CPU sampler and reuses the image after sampler edits") {
    MaterialTextureRegistry registry;
    const auto handle = tc_texture_create("material-sampler-test");
    tc_texture* texture = tc_texture_get(handle);
    REQUIRE(texture != nullptr);
    const uint8_t pixel[] = {255, 255, 255, 255};
    const tc_texture_pixel_data pixels{pixel, sizeof(pixel), 1, 1, 4};
    REQUIRE(tc_texture_set_data(texture, &pixels, nullptr, nullptr));
    auto sampler = tc_sampler_desc_default();
    sampler.min_filter = TC_SAMPLER_FILTER_NEAREST;
    sampler.mag_filter = TC_SAMPLER_FILTER_LINEAR;
    sampler.mip_filter = TC_SAMPLER_FILTER_NEAREST;
    sampler.address_v = TC_SAMPLER_ADDRESS_MIRRORED_REPEAT;
    sampler.address_w = TC_SAMPLER_ADDRESS_CLAMP_TO_EDGE;
    REQUIRE(tc_texture_set_sampler(texture, &sampler));
    const uint32_t original_version = texture->header.version;

    tc_shader_resource_binding resource{};
    std::snprintf(resource.name, sizeof(resource.name), "%s", "u_checker");
    resource.kind = TC_SHADER_RESOURCE_TEXTURE;
    resource.scope = TC_SHADER_RESOURCE_SCOPE_MATERIAL;
    resource.stage_mask = TC_SHADER_STAGE_FRAGMENT;
    tc_shader shader{};
    shader.has_resource_layout = 1;
    shader.resource_bindings = &resource;
    shader.resource_binding_count = 1;
    tc_material_texture entry{};
    std::snprintf(entry.name, sizeof(entry.name), "%s", "u_checker");
    entry.texture = handle;
    tc_material_phase phase{};
    phase.owner_material = tc_material_handle_invalid();
    phase.textures[0] = entry;
    phase.texture_count = 1;

    MaterialTextureDevice device;
    tgfx::PipelineCache cache(device);
    tgfx::RenderContext2 context(device, cache);
    context.begin_frame();
    tgfx::RenderPassDesc pass;
    pass.colors.resize(1);
    tgfx::TextureDesc target;
    target.usage = tgfx::TextureUsage::ColorAttachment;
    pass.colors[0].texture = device.create_texture(target);
    REQUIRE(context.begin_pass(pass));
    context.bind_shader(tgfx::ShaderHandle{1}, tgfx::ShaderHandle{2});
    context.use_shader_resource_layout(&shader);
    const auto draw = [&]() {
        REQUIRE(termin::apply_material_phase_ubo(&phase, &shader, device, context));
        context.draw_arrays(tgfx::BufferHandle{12}, 3);
    };
    draw();
    REQUIRE(device.samplers.size() == 1u);
    CHECK(device.samplers[0].min_filter == tgfx::FilterMode::Nearest);
    CHECK(device.samplers[0].mag_filter == tgfx::FilterMode::Linear);
    CHECK(device.samplers[0].mip_filter == tgfx::FilterMode::Nearest);
    CHECK(device.samplers[0].address_u == tgfx::AddressMode::Repeat);
    CHECK(device.samplers[0].address_v == tgfx::AddressMode::MirroredRepeat);
    CHECK(device.samplers[0].address_w == tgfx::AddressMode::ClampToEdge);
    REQUIRE(!device.bound_sets.empty());
    REQUIRE(device.bound_sets.back().size() == 1u);
    const auto first = device.bound_sets.back()[0].value;
    CHECK(first.texture.id == 101u);
    CHECK(first.sampler.id == 1u);

    sampler.min_filter = TC_SAMPLER_FILTER_LINEAR;
    sampler.address_u = TC_SAMPLER_ADDRESS_CLAMP_TO_EDGE;
    REQUIRE(tc_texture_set_sampler(texture, &sampler));
    draw();
    CHECK(texture->header.version == original_version);
    CHECK(device.image_uploads == 1u);
    REQUIRE(device.samplers.size() == 2u);
    REQUIRE(device.bound_sets.back().size() == 1u);
    CHECK(device.bound_sets.back()[0].value.texture == first.texture);
    CHECK(device.bound_sets.back()[0].value.sampler.id == 2u);
    draw();
    CHECK(device.samplers.size() == 2u);
    CHECK(device.image_uploads == 1u);

    tc_texture_set_mipmap(texture, !texture->mipmap);
    draw();
    CHECK(device.image_uploads == 2u);
    CHECK(device.samplers.size() == 2u);
    CHECK(device.bound_sets.back()[0].value.texture.id == 102u);
    CHECK(device.bound_sets.back()[0].value.sampler.id == 2u);
    context.end_pass();
    context.end_frame();
}

TEST_CASE("texture binding reacquires sampler state after lazy registry relocation") {
    MaterialTextureRegistry registry;
    MaterialTextureLoader loader;
    loader.handle = tc_texture_declare("material-lazy-sampler", "lazy sampler");
    tc_resource_set_loader(MaterialTextureLoader::load, &loader);
    MaterialTextureDevice device;
    const auto binding = termin::resolve_tc_texture_binding(device, loader.handle);
    REQUIRE(loader.relocated);
    CHECK(static_cast<bool>(binding.texture));
    CHECK(static_cast<bool>(binding.sampler));
    REQUIRE(device.samplers.size() == 1u);
    CHECK(device.samplers[0].address_u == tgfx::AddressMode::ClampToEdge);
    CHECK(device.samplers[0].min_filter == tgfx::FilterMode::Nearest);

    device.destroy_after_image = true;
    captured_log.clear();
    tc_log_set_callback(capture_log);
    const auto disappeared = termin::resolve_tc_texture_binding(device, loader.handle);
    tc_log_set_callback(nullptr);
    CHECK_FALSE(static_cast<bool>(disappeared.texture));
    CHECK_FALSE(static_cast<bool>(disappeared.sampler));
    CHECK(captured_log.find("disappeared") != std::string::npos);
    CHECK(device.samplers.size() == 1u);
}

TEST_CASE("material UBO Bool field packs Bool uniforms as int32") {
    std::array<uint8_t, 16> buffer{};
    const tc_uniform_value enabled = uniform_bool("u_enabled", true);

    REQUIRE(termin::pack_material_uniform_value_to_std140_field(enabled, "Bool", buffer.data()));

    CHECK_EQ(read_int_at(buffer, 0), 1);
}

TEST_CASE("material UBO Bool field accepts Int uniforms as 0 or 1") {
    std::array<uint8_t, 16> buffer{};
    tc_uniform_value disabled = uniform_int("u_disabled", 0);
    tc_uniform_value enabled = uniform_int("u_enabled", 42);

    REQUIRE(termin::pack_material_uniform_value_to_std140_field(disabled, "Bool", buffer.data()));
    REQUIRE(termin::pack_material_uniform_value_to_std140_field(enabled, "Bool", buffer.data() + 4));

    CHECK_EQ(read_int_at(buffer, 0), 0);
    CHECK_EQ(read_int_at(buffer, 4), 1);
}

TEST_CASE("material UBO Bool field rejects non-integral uniforms") {
    std::array<uint8_t, 16> buffer{};
    buffer[0] = 0xCD;
    buffer[1] = 0xCD;
    buffer[2] = 0xCD;
    buffer[3] = 0xCD;
    const tc_uniform_value value = uniform_float("u_enabled", 1.0f);

    captured_log.clear();
    tc_log_set_callback(capture_log);
    const bool packed = termin::pack_material_uniform_value_to_std140_field(value, "Bool", buffer.data());
    tc_log_set_callback(nullptr);

    CHECK(!packed);

    CHECK_EQ(buffer[0], 0xCD);
    CHECK_EQ(buffer[1], 0xCD);
    CHECK_EQ(buffer[2], 0xCD);
    CHECK_EQ(buffer[3], 0xCD);
    CHECK(captured_log.find("u_enabled") != std::string::npos);
    CHECK(captured_log.find("Float") != std::string::npos);
    CHECK(captured_log.find("Bool") != std::string::npos);
}

TEST_CASE("material UBO authored #808080 decodes once and preserves alpha") {
    std::array<uint8_t, 16> buffer{};
    constexpr float authored = 128.0f / 255.0f;
    const tc_uniform_value value = uniform_color("u_color", TC_UNIFORM_SRGB_COLOR, authored, authored, authored, 0.5f);

    REQUIRE(termin::pack_material_uniform_value_to_std140_field(value, "SrgbColor", buffer.data()));

    CHECK(std::fabs(read_float_at(buffer, 0) - 0.2158605f) < 1.0e-5f);
    CHECK(std::fabs(read_float_at(buffer, 4) - 0.2158605f) < 1.0e-5f);
    CHECK(std::fabs(read_float_at(buffer, 8) - 0.2158605f) < 1.0e-5f);
    CHECK_EQ(read_float_at(buffer, 12), 0.5f);
}

TEST_CASE("material UBO reflected Vec4 preserves authored color semantics") {
    std::array<uint8_t, 16> buffer{};
    constexpr float authored = 128.0f / 255.0f;
    const tc_uniform_value srgb =
        uniform_color("u_srgb", TC_UNIFORM_SRGB_COLOR, authored, authored, authored, 0.25f);

    REQUIRE(termin::pack_material_uniform_value_to_std140_field(srgb, "Vec4", buffer.data()));
    CHECK(std::fabs(read_float_at(buffer, 0) - 0.2158605f) < 1.0e-5f);
    CHECK(std::fabs(read_float_at(buffer, 4) - 0.2158605f) < 1.0e-5f);
    CHECK(std::fabs(read_float_at(buffer, 8) - 0.2158605f) < 1.0e-5f);
    CHECK_EQ(read_float_at(buffer, 12), 0.25f);

    const tc_uniform_value linear =
        uniform_color("u_linear", TC_UNIFORM_LINEAR_COLOR, 4.0f, 0.5f, -2.0f, 0.75f);
    REQUIRE(termin::pack_material_uniform_value_to_std140_field(linear, "Vec4", buffer.data()));
    CHECK_EQ(read_float_at(buffer, 0), 4.0f);
    CHECK_EQ(read_float_at(buffer, 4), 0.5f);
    CHECK_EQ(read_float_at(buffer, 8), -2.0f);
    CHECK_EQ(read_float_at(buffer, 12), 0.75f);
}

TEST_CASE("material UBO LinearColor and Vec4 preserve literal values including HDR") {
    std::array<uint8_t, 16> buffer{};
    const tc_uniform_value linear = uniform_color("u_linear", TC_UNIFORM_LINEAR_COLOR, 4.0f, 0.5f, -2.0f, 0.5f);
    const tc_uniform_value vec4 = uniform_color("u_vec4", TC_UNIFORM_VEC4, 0.5f, 0.5f, 0.5f, 0.5f);

    REQUIRE(termin::pack_material_uniform_value_to_std140_field(linear, "LinearColor", buffer.data()));
    CHECK_EQ(read_float_at(buffer, 0), 4.0f);
    CHECK_EQ(read_float_at(buffer, 4), 0.5f);
    CHECK_EQ(read_float_at(buffer, 8), -2.0f);
    CHECK_EQ(read_float_at(buffer, 12), 0.5f);

    REQUIRE(termin::pack_material_uniform_value_to_std140_field(vec4, "Vec4", buffer.data()));
    CHECK_EQ(read_float_at(buffer, 0), 0.5f);
}

TEST_CASE("material UBO color fields reject cross-kind and legacy Color values") {
    std::array<uint8_t, 16> buffer{};
    buffer.fill(0xCD);
    const tc_uniform_value srgb = uniform_color("u_color", TC_UNIFORM_SRGB_COLOR, 0.5f, 0.5f, 0.5f, 0.5f);
    const tc_uniform_value linear = uniform_color("u_color", TC_UNIFORM_LINEAR_COLOR, 0.5f, 0.5f, 0.5f, 0.5f);
    const tc_uniform_value vec4 = uniform_color("u_color", TC_UNIFORM_VEC4, 0.5f, 0.5f, 0.5f, 0.5f);

    captured_log.clear();
    tc_log_set_callback(capture_log);
    CHECK(!termin::pack_material_uniform_value_to_std140_field(srgb, "LinearColor", buffer.data()));
    CHECK(!termin::pack_material_uniform_value_to_std140_field(linear, "SrgbColor", buffer.data()));
    CHECK(!termin::pack_material_uniform_value_to_std140_field(vec4, "Color", buffer.data()));
    tc_log_set_callback(nullptr);

    CHECK_EQ(buffer[0], 0xCD);
    CHECK(captured_log.find("u_color") != std::string::npos);
    CHECK(captured_log.find("incompatible") != std::string::npos);
}

namespace {
    struct MaterialPackingFixture {
        tc_material_phase phase{};
        tc_shader shader{};
        tc_material_ubo_entry authored{};
        tc_shader_resource_field reflected{};
        tc_shader_resource_binding binding{};
        tgfx::FrameDataCache cache;

        MaterialPackingFixture() {
            phase.uniform_count = 1;
            phase.uniforms[0] = uniform_float("u_value", 0.25f);
            std::snprintf(authored.name, sizeof(authored.name), "u_value");
            std::snprintf(authored.property_type, sizeof(authored.property_type), "Float");
            authored.size = 4;
            shader.material_ubo_entries = &authored;
            shader.material_ubo_entry_count = 1;
            shader.material_ubo_block_size = 16;
            std::snprintf(reflected.name, sizeof(reflected.name), "u_value");
            std::snprintf(reflected.type, sizeof(reflected.type), "Float");
            reflected.size = 4;
            std::snprintf(binding.name, sizeof(binding.name), TC_SHADER_RESOURCE_MATERIAL);
            binding.kind = TC_SHADER_RESOURCE_CONSTANT_BUFFER;
            binding.scope = TC_SHADER_RESOURCE_SCOPE_MATERIAL;
            binding.fields = &reflected;
            binding.field_count = 1;
            binding.size = 16;
            shader.resource_bindings = &binding;
            shader.resource_binding_count = 1;
        }

        std::span<const uint8_t> pack() {
            return termin::pack_material_phase_uniforms(&phase, &shader, cache);
        }
    };

    float packed_float(std::span<const uint8_t> bytes, size_t offset) {
        float value = 0;
        std::memcpy(&value, bytes.data() + offset, sizeof(value));
        return value;
    }
}

TEST_CASE("material packing reuses bytes and observes same-frame public uniform edits") {
    MaterialPackingFixture fixture;
    const auto first = fixture.pack();
    REQUIRE_EQ(first.size(), 16u);
    CHECK_EQ(packed_float(first, 0), 0.25f);
    CHECK_EQ(fixture.pack().data(), first.data());
    fixture.phase.uniforms[0].data.f = 0.75f;
    CHECK_EQ(packed_float(fixture.pack(), 0), 0.75f);
    fixture.phase.uniform_count = 0;
    CHECK_EQ(packed_float(fixture.pack(), 0), 0.0f);
    fixture.phase.uniform_count = 1;
    std::snprintf(fixture.phase.uniforms[0].name, sizeof(fixture.phase.uniforms[0].name), "u_other");
    CHECK_EQ(packed_float(fixture.pack(), 0), 0.0f);
}

TEST_CASE("material packing detects authored layout edits without shader version changes") {
    MaterialPackingFixture fixture;
    REQUIRE_EQ(fixture.pack().size(), 16u);
    fixture.authored.offset = 8;
    const auto moved = fixture.pack();
    REQUIRE_EQ(moved.size(), 16u);
    CHECK_EQ(packed_float(moved, 0), 0.0f);
    CHECK_EQ(packed_float(moved, 8), 0.25f);
    fixture.shader.material_ubo_block_size = 32;
    CHECK_EQ(fixture.pack().size(), 32u);
    fixture.authored.offset = 31;
    CHECK(fixture.pack().empty());
    fixture.authored.offset = 4;
    CHECK_EQ(packed_float(fixture.pack(), 4), 0.25f);
    fixture.shader.material_ubo_entry_count = 0;
    fixture.shader.resource_binding_count = 0;
    CHECK(fixture.pack().empty());
}

TEST_CASE("material packing detects reflected layout and type edits without version changes") {
    MaterialPackingFixture fixture;
    fixture.shader.material_ubo_entry_count = 0;
    fixture.shader.material_ubo_block_size = 0;
    REQUIRE_EQ(fixture.pack().size(), 16u);
    fixture.reflected.offset = 4;
    const auto moved = fixture.pack();
    CHECK_EQ(packed_float(moved, 0), 0.0f);
    CHECK_EQ(packed_float(moved, 4), 0.25f);
    std::snprintf(fixture.reflected.type, sizeof(fixture.reflected.type), "Vec3");
    CHECK(fixture.pack().empty());
    std::snprintf(fixture.reflected.type, sizeof(fixture.reflected.type), "Float");
    fixture.binding.size = 32;
    CHECK_EQ(fixture.pack().size(), 32u);
    fixture.shader.version++;
    CHECK_EQ(packed_float(fixture.pack(), 4), 0.25f);
}

TEST_CASE("material packing retains color conversion and observes type changes") {
    MaterialPackingFixture fixture;
    std::snprintf(fixture.authored.property_type, sizeof(fixture.authored.property_type), "Vec4");
    fixture.authored.size = 16;
    fixture.phase.uniforms[0] = uniform_color("u_value", TC_UNIFORM_SRGB_COLOR, 0.5f, 0.5f, 0.5f, 1.0f);
    const auto srgb = fixture.pack();
    REQUIRE_EQ(srgb.size(), 16u);
    CHECK(std::abs(packed_float(srgb, 0) - 0.21404114f) < 0.000001f);
    fixture.phase.uniforms[0] = uniform_color("u_value", TC_UNIFORM_LINEAR_COLOR, 0.5f, 0.5f, 0.5f, 1.0f);
    CHECK_EQ(packed_float(fixture.pack(), 0), 0.5f);
}

TEST_CASE("frame data cache verifies bytes and segment boundaries despite identical hints") {
    tgfx::FrameDataCache cache;
    const uint8_t domain_a = 0, domain_b = 0;
    uint8_t source[] = {1, 2, 3, 4};
    const tgfx::FrameDataInput inputs[] = {{source, 2}, {source + 2, 2}};
    cache.store(&domain_a, 123, inputs, {7});
    REQUIRE_EQ(cache.find(&domain_a, 123, inputs).size(), 1u);
    CHECK_EQ(cache.find(&domain_a, 123, inputs)[0], 7);
    CHECK(cache.find(&domain_b, 123, inputs).empty());
    const tgfx::FrameDataInput other_boundaries[] = {{source, 1}, {source + 1, 3}};
    CHECK(cache.find(&domain_a, 123, other_boundaries).empty());
    source[0] = 9;
    CHECK(cache.find(&domain_a, 123, inputs).empty());
    cache.store(&domain_a, 123, inputs, {8});
    CHECK_EQ(cache.find(&domain_a, 123, inputs)[0], 8);
    source[0] = 1;
    CHECK(cache.find(&domain_a, 123, inputs).empty());
    cache.clear();
    CHECK(cache.find(&domain_a, 123, inputs).empty());
}
