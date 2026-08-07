#include "termin/lighting/lighting_ubo.hpp"

#include <algorithm>

namespace termin {

    LightingUBO::LightingUBO()
        : data{} {}

    LightingUBO::~LightingUBO() {
        destroy();
    }

    void LightingUBO::create(tgfx::IRenderDevice& device) {
        if (buffer && device_ == &device)
            return;
        destroy();
        tgfx::BufferDesc desc;
        desc.size = sizeof(LightingUBOData);
        desc.usage = tgfx::BufferUsage::Uniform | tgfx::BufferUsage::CopyDst;
        buffer = device.create_buffer(desc);
        device_ = &device;
    }

    void LightingUBO::destroy() {
        if (buffer && device_)
            device_->destroy(buffer);
        buffer = {};
        device_ = nullptr;
    }

    void LightingUBO::update_from_lights(std::span<const Light> lights,
                                         const Vec3& ambient_color,
                                         float ambient_intensity,
                                         const Vec3& camera_position,
                                         const ShadowSettings& shadow_settings) {
        int count = static_cast<int>(std::min(lights.size(), static_cast<size_t>(UBO_MAX_LIGHTS)));
        for (int i = 0; i < count; ++i) {
            const Light& light = lights[i];
            LightDataStd140& ld = data.lights[i];
            ld.color = Vec3f{float(light.color.x), float(light.color.y), float(light.color.z)};
            ld.intensity = float(light.intensity);
            ld.direction = Vec3f{float(light.direction.x), float(light.direction.y), float(light.direction.z)};
            ld.range = light.range ? float(*light.range) : 1e9f;
            ld.position = Vec3f{float(light.position.x), float(light.position.y), float(light.position.z)};
            ld.type = light.type == LightType::Directional ? 0.0f : light.type == LightType::Point ? 1.0f : 2.0f;
            ld.attenuation = Vec3f{
                float(light.attenuation.constant), float(light.attenuation.linear), float(light.attenuation.quadratic)};
            ld.inner_angle = float(light.inner_angle);
            ld.outer_angle = float(light.outer_angle);
            ld.cascade_count = float(light.shadows.cascade_count);
            ld.cascade_blend = light.shadows.cascade_blend ? 1.0f : 0.0f;
            ld.blend_distance = light.shadows.blend_distance;
        }
        for (int i = count; i < UBO_MAX_LIGHTS; ++i)
            data.lights[i] = {};
        data.ambient_color = Vec3f{float(ambient_color.x), float(ambient_color.y), float(ambient_color.z)};
        data.ambient_intensity = ambient_intensity;
        data.camera_position = Vec3f{float(camera_position.x), float(camera_position.y), float(camera_position.z)};
        data.light_count = float(count);
        data.shadow_method = float(shadow_settings.method);
        data.shadow_softness = float(shadow_settings.softness);
        data.shadow_bias = float(shadow_settings.bias);
        data._pad0 = 0.0f;
    }

    void LightingUBO::upload() {
        if (!buffer || !device_)
            return;
        device_->upload_buffer(buffer, std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(&data), sizeof(data)));
    }

} // namespace termin
