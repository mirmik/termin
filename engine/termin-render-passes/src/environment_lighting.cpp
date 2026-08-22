#include <termin/lighting/environment_lighting.hpp>

#include <termin/geom/color.hpp>
#include <termin/geom/vec3.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/frame_graph_resource_registry.hpp>
#include <termin/render/scene_render_services.hpp>

#include <tgfx2/descriptors.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/render_context.hpp>

extern "C" {
#include <core/tc_scene_render_state.h>
#include <core/tc_scene_skybox.h>
}

#include <tcbase/tc_log.hpp>

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <span>
#include <vector>

namespace termin {
    namespace {

        constexpr uint32_t kDiffuseSize = 16;
        constexpr uint32_t kSpecularSize = 64;
        constexpr uint32_t kSpecularMipCount = 7;
        constexpr uint32_t kBrdfSize = 128;
        constexpr uint32_t kDiffuseSamples = 128;
        constexpr uint32_t kSpecularSamples = 128;
        constexpr uint32_t kBrdfSamples = 128;
        constexpr float kPi = 3.14159265358979323846f;

        float sign_not_zero(float value) {
            return value < 0.0f ? -1.0f : 1.0f;
        }

        Vec3f octahedral_decode(float u, float v) {
            float x = u * 2.0f - 1.0f;
            float y = v * 2.0f - 1.0f;
            const float z = 1.0f - std::abs(x) - std::abs(y);
            if (z < 0.0f) {
                const float old_x = x;
                x = (1.0f - std::abs(y)) * sign_not_zero(old_x);
                y = (1.0f - std::abs(old_x)) * sign_not_zero(y);
            }
            return Vec3f{x, y, z}.normalized_or(Vec3f::unit_z(), 1.0e-10f);
        }

        float radical_inverse_vdc(uint32_t bits) {
            bits = (bits << 16u) | (bits >> 16u);
            bits = ((bits & 0x55555555u) << 1u) | ((bits & 0xAAAAAAAAu) >> 1u);
            bits = ((bits & 0x33333333u) << 2u) | ((bits & 0xCCCCCCCCu) >> 2u);
            bits = ((bits & 0x0F0F0F0Fu) << 4u) | ((bits & 0xF0F0F0F0u) >> 4u);
            bits = ((bits & 0x00FF00FFu) << 8u) | ((bits & 0xFF00FF00u) >> 8u);
            return static_cast<float>(bits) * 2.3283064365386963e-10f;
        }

        std::array<float, 2> hammersley(uint32_t index, uint32_t count) {
            return {static_cast<float>(index) / static_cast<float>(count), radical_inverse_vdc(index)};
        }

        void make_basis(const Vec3f& normal, Vec3f& tangent, Vec3f& bitangent) {
            const Vec3f up = std::abs(normal.z) < 0.999f ? Vec3f::unit_z() : Vec3f::unit_x();
            tangent = up.cross(normal).normalized_or(Vec3f::unit_z(), 1.0e-10f);
            bitangent = normal.cross(tangent);
        }

        Vec3f tangent_to_world(const Vec3f& local, const Vec3f& normal) {
            Vec3f tangent;
            Vec3f bitangent;
            make_basis(normal, tangent, bitangent);
            return (tangent * local.x + bitangent * local.y + normal * local.z)
                .normalized_or(Vec3f::unit_z(), 1.0e-10f);
        }

        Vec3f cosine_sample_hemisphere(std::array<float, 2> xi, const Vec3f& normal) {
            const float radius = std::sqrt(xi[0]);
            const float phi = 2.0f * kPi * xi[1];
            return tangent_to_world(
                {radius * std::cos(phi), radius * std::sin(phi), std::sqrt(std::max(0.0f, 1.0f - xi[0]))},
                normal);
        }

        Vec3f importance_sample_ggx(std::array<float, 2> xi, const Vec3f& normal, float roughness) {
            const float alpha = roughness * roughness;
            const float alpha_squared = alpha * alpha;
            const float phi = 2.0f * kPi * xi[0];
            const float cosine = std::sqrt((1.0f - xi[1]) / (1.0f + (alpha_squared - 1.0f) * xi[1]));
            const float sine = std::sqrt(std::max(0.0f, 1.0f - cosine * cosine));
            return tangent_to_world({std::cos(phi) * sine, std::sin(phi) * sine, cosine}, normal);
        }

        Vec3f sample_environment(const std::array<float, 16>& signature, const Vec3f& direction) {
            const int skybox_type = static_cast<int>(signature[0]);
            const Vec3f solid{signature[1], signature[2], signature[3]};
            const Vec3f top{signature[4], signature[5], signature[6]};
            const Vec3f horizon{signature[7], signature[8], signature[9]};
            const Vec3f bottom{signature[10], signature[11], signature[12]};
            const float top_exponent = std::max(signature[13], 0.001f);
            const float bottom_exponent = std::max(signature[14], 0.001f);
            const float intensity = std::max(0.0f, signature[15]);

            Vec3f radiance;
            if (skybox_type == TC_SKYBOX_GRADIENT) {
                const float height = std::clamp(direction.z, -1.0f, 1.0f);
                if (height >= 0.0f) {
                    const float t = std::pow(height, top_exponent);
                    radiance = horizon * (1.0f - t) + top * t;
                } else {
                    const float t = std::pow(-height, bottom_exponent);
                    radiance = horizon * (1.0f - t) + bottom * t;
                }
            } else {
                // A hidden sky still retains scene ambient illumination; solid
                // sky uses its authored color as the environment.
                radiance = solid;
            }
            return radiance * intensity;
        }

        std::vector<float> build_diffuse_irradiance(const std::array<float, 16>& signature) {
            std::vector<float> pixels(kDiffuseSize * kDiffuseSize * 4u);
            for (uint32_t y = 0; y < kDiffuseSize; ++y) {
                for (uint32_t x = 0; x < kDiffuseSize; ++x) {
                    const Vec3f normal = octahedral_decode((x + 0.5f) / kDiffuseSize, (y + 0.5f) / kDiffuseSize);
                    Vec3f average{};
                    for (uint32_t sample = 0; sample < kDiffuseSamples; ++sample) {
                        average += sample_environment(signature,
                                                      cosine_sample_hemisphere(hammersley(sample, kDiffuseSamples),
                                                                               normal));
                    }
                    const Vec3f irradiance = average * (kPi / static_cast<float>(kDiffuseSamples));
                    const size_t offset = (static_cast<size_t>(y) * kDiffuseSize + x) * 4u;
                    pixels[offset + 0] = irradiance.x;
                    pixels[offset + 1] = irradiance.y;
                    pixels[offset + 2] = irradiance.z;
                    pixels[offset + 3] = 1.0f;
                }
            }
            return pixels;
        }

        std::vector<std::vector<float>> build_prefiltered_specular(const std::array<float, 16>& signature) {
            std::vector<std::vector<float>> mips;
            mips.reserve(kSpecularMipCount);
            for (uint32_t mip = 0; mip < kSpecularMipCount; ++mip) {
                const uint32_t size = std::max(1u, kSpecularSize >> mip);
                const float roughness = static_cast<float>(mip) / static_cast<float>(kSpecularMipCount - 1u);
                std::vector<float> pixels(size * size * 4u);
                for (uint32_t y = 0; y < size; ++y) {
                    for (uint32_t x = 0; x < size; ++x) {
                        const Vec3f normal = octahedral_decode((x + 0.5f) / size, (y + 0.5f) / size);
                        Vec3f filtered{};
                        float total_weight = 0.0f;
                        if (mip == 0) {
                            filtered = sample_environment(signature, normal);
                            total_weight = 1.0f;
                        } else {
                            for (uint32_t sample = 0; sample < kSpecularSamples; ++sample) {
                                const Vec3f half_vector = importance_sample_ggx(
                                    hammersley(sample, kSpecularSamples), normal, roughness);
                                const Vec3f light =
                                    (half_vector * (2.0f * normal.dot(half_vector)) - normal)
                                        .normalized_or(Vec3f::unit_z(), 1.0e-10f);
                                const float weight = std::max(normal.dot(light), 0.0f);
                                if (weight > 0.0f) {
                                    filtered += sample_environment(signature, light) * weight;
                                    total_weight += weight;
                                }
                            }
                        }
                        filtered = filtered * (1.0f / std::max(total_weight, 1.0e-6f));
                        const size_t offset = (static_cast<size_t>(y) * size + x) * 4u;
                        pixels[offset + 0] = filtered.x;
                        pixels[offset + 1] = filtered.y;
                        pixels[offset + 2] = filtered.z;
                        pixels[offset + 3] = 1.0f;
                    }
                }
                mips.push_back(std::move(pixels));
            }
            return mips;
        }

        float geometry_schlick_ggx(float cosine, float roughness) {
            const float k = roughness * roughness * 0.5f;
            return cosine / (cosine * (1.0f - k) + k);
        }

        std::vector<float> build_brdf_lut() {
            std::vector<float> pixels(kBrdfSize * kBrdfSize * 2u);
            const Vec3f normal = Vec3f::unit_z();
            for (uint32_t y = 0; y < kBrdfSize; ++y) {
                const float roughness = (y + 0.5f) / kBrdfSize;
                for (uint32_t x = 0; x < kBrdfSize; ++x) {
                    const float normal_dot_view = std::max((x + 0.5f) / kBrdfSize, 1.0e-4f);
                    const Vec3f view{std::sqrt(std::max(0.0f, 1.0f - normal_dot_view * normal_dot_view)),
                                     0.0f,
                                     normal_dot_view};
                    float scale = 0.0f;
                    float bias = 0.0f;
                    for (uint32_t sample = 0; sample < kBrdfSamples; ++sample) {
                        const Vec3f half_vector =
                            importance_sample_ggx(hammersley(sample, kBrdfSamples), normal, roughness);
                        const Vec3f light = (half_vector * (2.0f * view.dot(half_vector)) - view)
                                                .normalized_or(Vec3f::unit_z(), 1.0e-10f);
                        const float normal_dot_light = std::max(light.z, 0.0f);
                        const float normal_dot_half = std::max(half_vector.z, 0.0f);
                        const float view_dot_half = std::max(view.dot(half_vector), 0.0f);
                        if (normal_dot_light <= 0.0f) {
                            continue;
                        }
                        const float geometry = geometry_schlick_ggx(normal_dot_view, roughness) *
                                               geometry_schlick_ggx(normal_dot_light, roughness);
                        const float visibility = geometry * view_dot_half /
                                                 std::max(normal_dot_half * normal_dot_view, 1.0e-6f);
                        const float fresnel = std::pow(1.0f - view_dot_half, 5.0f);
                        scale += (1.0f - fresnel) * visibility;
                        bias += fresnel * visibility;
                    }
                    const size_t offset = (static_cast<size_t>(y) * kBrdfSize + x) * 2u;
                    pixels[offset + 0] = scale / static_cast<float>(kBrdfSamples);
                    pixels[offset + 1] = bias / static_cast<float>(kBrdfSamples);
                }
            }
            return pixels;
        }

        std::span<const uint8_t> byte_span(const std::vector<float>& values) {
            return {reinterpret_cast<const uint8_t*>(values.data()), values.size() * sizeof(float)};
        }

        FrameGraphResource* create_environment_lighting(const ResourceSpec&) {
            return new EnvironmentLightingResource();
        }

        FrameGraphResourceSampledTexture environment_lighting_sampled_texture(const FrameGraphResource& resource) {
            const auto& environment = static_cast<const EnvironmentLightingResource&>(resource);
            return {
                .texture = environment.prefiltered_specular,
                .kind = FrameGraphResourceSampledTextureKind::Color,
            };
        }

    } // namespace

    bool register_environment_lighting_resource_type() {
        const FrameGraphResourceTypeDescriptor descriptor{
            .resource_type = "environment_lighting",
            .create = create_environment_lighting,
            .sampled_texture = environment_lighting_sampled_texture,
        };
        if (frame_graph_resource_type_matches(descriptor)) {
            return true;
        }
        return register_frame_graph_resource_type(descriptor);
    }

    EnvironmentLightingPass::EnvironmentLightingPass(const std::string& output, const std::string& pass_name)
        : output_res(output) {
        pass_name_set(pass_name);
        link_to_type_registry("EnvironmentLightingPass");
    }

    std::set<const char*> EnvironmentLightingPass::compute_reads() const {
        return {};
    }

    std::set<const char*> EnvironmentLightingPass::compute_writes() const {
        return {output_res.c_str()};
    }

    std::vector<ResourceSpec> EnvironmentLightingPass::get_resource_specs() const {
        return {ResourceSpec{output_res, "environment_lighting", std::nullopt, std::nullopt, std::nullopt}};
    }

    void EnvironmentLightingPass::execute(ExecuteContext& ctx) {
        if (!ctx.ctx2) {
            tc::Log::error("[EnvironmentLightingPass] ctx2 is null — tgfx2 path required");
            return;
        }
        const SceneRenderServices* services = require_scene_render_services(ctx, "EnvironmentLightingPass");
        if (!services) {
            return;
        }
        EnvironmentLightingResource* output =
            ctx.get_frame_graph_resource_as<EnvironmentLightingResource>(output_res);
        if (!output) {
            tc::Log::error("[EnvironmentLightingPass] output '%s' is not an environment_lighting resource",
                           output_res.c_str());
            return;
        }

        tgfx::IRenderDevice& device = ctx.ctx2->device();
        if (device_ && device_ != &device) {
            destroy_gpu_resources();
        }
        device_ = &device;

        const tc_scene_handle scene = services->scene.handle();
        std::array<float, 16> signature{};
        signature[0] = static_cast<float>(tc_scene_get_skybox_type(scene));
        tc_srgb_color solid{};
        tc_srgb_color top{};
        tc_srgb_color horizon{};
        tc_srgb_color bottom{};
        tc_scene_get_skybox_srgb_color(scene, &solid);
        tc_scene_get_skybox_top_srgb_color(scene, &top);
        tc_scene_get_skybox_horizon_srgb_color(scene, &horizon);
        tc_scene_get_skybox_bottom_srgb_color(scene, &bottom);
        const LinearColor solid_linear = srgb_to_linear({solid.r, solid.g, solid.b, 1.0f});
        const LinearColor top_linear = srgb_to_linear({top.r, top.g, top.b, 1.0f});
        const LinearColor horizon_linear = srgb_to_linear({horizon.r, horizon.g, horizon.b, 1.0f});
        const LinearColor bottom_linear = srgb_to_linear({bottom.r, bottom.g, bottom.b, 1.0f});
        signature[1] = solid_linear.r; signature[2] = solid_linear.g; signature[3] = solid_linear.b;
        signature[4] = top_linear.r; signature[5] = top_linear.g; signature[6] = top_linear.b;
        signature[7] = horizon_linear.r; signature[8] = horizon_linear.g; signature[9] = horizon_linear.b;
        signature[10] = bottom_linear.r; signature[11] = bottom_linear.g; signature[12] = bottom_linear.b;
        signature[13] = tc_scene_get_skybox_top_exponent(scene);
        signature[14] = tc_scene_get_skybox_bottom_exponent(scene);

        tc_scene_render_state* render_state = tc_scene_render_state_get(scene);
        const tc_scene_lighting* lighting = render_state ? &render_state->lighting : nullptr;
        if (lighting) {
            const LinearColor ambient_linear = srgb_to_linear({lighting->ambient_color.r,
                                                               lighting->ambient_color.g,
                                                               lighting->ambient_color.b,
                                                               1.0f});
            const Vec3f ambient_tint{ambient_linear.r, ambient_linear.g, ambient_linear.b};
            const float intensity = std::max(0.0f, lighting->ambient_intensity);
            signature[1] *= ambient_tint.x;
            signature[2] *= ambient_tint.y;
            signature[3] *= ambient_tint.z;
            signature[4] *= ambient_tint.x;
            signature[5] *= ambient_tint.y;
            signature[6] *= ambient_tint.z;
            signature[7] *= ambient_tint.x;
            signature[8] *= ambient_tint.y;
            signature[9] *= ambient_tint.z;
            signature[10] *= ambient_tint.x;
            signature[11] *= ambient_tint.y;
            signature[12] *= ambient_tint.z;
            signature[15] = intensity;
        } else {
            signature[15] = 0.1f;
        }

        const bool resources_ready = diffuse_irradiance_ && prefiltered_specular_ && brdf_lut_ && sampler_;
        if (!resources_ready || !has_cached_signature_ || signature != cached_signature_) {
            if (!resources_ready) {
                destroy_gpu_resources();

                tgfx::TextureDesc diffuse_desc;
                diffuse_desc.width = kDiffuseSize;
                diffuse_desc.height = kDiffuseSize;
                diffuse_desc.format = tgfx::PixelFormat::RGBA32F;
                diffuse_desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopyDst;
                diffuse_irradiance_ = device.create_texture(diffuse_desc);

                tgfx::TextureDesc specular_desc;
                specular_desc.width = kSpecularSize;
                specular_desc.height = kSpecularSize;
                specular_desc.mip_levels = kSpecularMipCount;
                specular_desc.format = tgfx::PixelFormat::RGBA32F;
                specular_desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopyDst;
                prefiltered_specular_ = device.create_texture(specular_desc);

                tgfx::TextureDesc brdf_desc;
                brdf_desc.width = kBrdfSize;
                brdf_desc.height = kBrdfSize;
                brdf_desc.format = tgfx::PixelFormat::RG32F;
                brdf_desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopyDst;
                brdf_lut_ = device.create_texture(brdf_desc);

                tgfx::SamplerDesc sampler_desc;
                sampler_desc.min_filter = tgfx::FilterMode::Linear;
                sampler_desc.mag_filter = tgfx::FilterMode::Linear;
                sampler_desc.mip_filter = tgfx::FilterMode::Linear;
                sampler_desc.address_u = tgfx::AddressMode::ClampToEdge;
                sampler_desc.address_v = tgfx::AddressMode::ClampToEdge;
                sampler_desc.address_w = tgfx::AddressMode::ClampToEdge;
                sampler_ = device.create_sampler(sampler_desc);

                if (!diffuse_irradiance_ || !prefiltered_specular_ || !brdf_lut_ || !sampler_) {
                    tc::Log::error("[EnvironmentLightingPass] failed to allocate IBL textures or sampler");
                    destroy_gpu_resources();
                    output->clear();
                    return;
                }

                const std::vector<float> brdf = build_brdf_lut();
                device.upload_texture(brdf_lut_, byte_span(brdf));
            }

            const std::vector<float> diffuse = build_diffuse_irradiance(signature);
            device.upload_texture(diffuse_irradiance_, byte_span(diffuse));
            const std::vector<std::vector<float>> specular = build_prefiltered_specular(signature);
            for (uint32_t mip = 0; mip < specular.size(); ++mip) {
                device.upload_texture(prefiltered_specular_, byte_span(specular[mip]), mip);
            }
            cached_signature_ = signature;
            has_cached_signature_ = true;
        }

        output->diffuse_irradiance = diffuse_irradiance_;
        output->prefiltered_specular = prefiltered_specular_;
        output->brdf_lut = brdf_lut_;
        output->sampler = sampler_;
        output->specular_mip_count = kSpecularMipCount;
    }

    void EnvironmentLightingPass::destroy_gpu_resources() {
        if (device_) {
            if (diffuse_irradiance_) {
                device_->destroy(diffuse_irradiance_);
            }
            if (prefiltered_specular_) {
                device_->destroy(prefiltered_specular_);
            }
            if (brdf_lut_) {
                device_->destroy(brdf_lut_);
            }
            if (sampler_) {
                device_->destroy(sampler_);
            }
        }
        diffuse_irradiance_ = {};
        prefiltered_specular_ = {};
        brdf_lut_ = {};
        sampler_ = {};
        has_cached_signature_ = false;
    }

    void EnvironmentLightingPass::destroy() {
        destroy_gpu_resources();
        device_ = nullptr;
    }

    void EnvironmentLightingPass::register_type() {
        auto descriptor =
            FramePassTypeDescriptorBuilder::native<EnvironmentLightingPass>("EnvironmentLightingPass",
                                                                            "termin-render-passes");
        auto& inspect = descriptor.inspect();
        _register_inspect_output_res(inspect);
        _register_inspect_metadata_graph(inspect);
        (void)descriptor.commit();
    }

} // namespace termin
