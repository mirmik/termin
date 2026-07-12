#include "termin/lighting/lighting_ubo.hpp"

#include <algorithm>
#include <cstring>

namespace termin {

LightingUBO::LightingUBO() { std::memset(&data, 0, sizeof(data)); }

LightingUBO::~LightingUBO() { destroy(); }

void LightingUBO::create(tgfx::IRenderDevice &device) {
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

void LightingUBO::update_from_lights(std::span<const Light> lights, const Vec3 &ambient_color,
                                     float ambient_intensity, const Vec3 &camera_position,
                                     const ShadowSettings &shadow_settings) {
    int count = static_cast<int>(std::min(lights.size(), static_cast<size_t>(UBO_MAX_LIGHTS)));
    for (int i = 0; i < count; ++i) {
        const Light &light = lights[i];
        LightDataStd140 &ld = data.lights[i];
        ld.color[0] = float(light.color.x);
        ld.color[1] = float(light.color.y);
        ld.color[2] = float(light.color.z);
        ld.intensity = float(light.intensity);
        ld.direction[0] = float(light.direction.x);
        ld.direction[1] = float(light.direction.y);
        ld.direction[2] = float(light.direction.z);
        ld.range = light.range ? float(*light.range) : 1e9f;
        ld.position[0] = float(light.position.x);
        ld.position[1] = float(light.position.y);
        ld.position[2] = float(light.position.z);
        ld.type = light.type == LightType::Directional ? 0.0f
                  : light.type == LightType::Point     ? 1.0f
                                                       : 2.0f;
        ld.attenuation[0] = float(light.attenuation.constant);
        ld.attenuation[1] = float(light.attenuation.linear);
        ld.attenuation[2] = float(light.attenuation.quadratic);
        ld.inner_angle = float(light.inner_angle);
        ld.outer_angle = float(light.outer_angle);
        ld.cascade_count = float(light.shadows.cascade_count);
        ld.cascade_blend = light.shadows.cascade_blend ? 1.0f : 0.0f;
        ld.blend_distance = light.shadows.blend_distance;
    }
    for (int i = count; i < UBO_MAX_LIGHTS; ++i)
        std::memset(&data.lights[i], 0, sizeof(LightDataStd140));
    data.ambient_color[0] = float(ambient_color.x);
    data.ambient_color[1] = float(ambient_color.y);
    data.ambient_color[2] = float(ambient_color.z);
    data.ambient_intensity = ambient_intensity;
    data.camera_position[0] = float(camera_position.x);
    data.camera_position[1] = float(camera_position.y);
    data.camera_position[2] = float(camera_position.z);
    data.light_count = float(count);
    data.shadow_method = float(shadow_settings.method);
    data.shadow_softness = float(shadow_settings.softness);
    data.shadow_bias = float(shadow_settings.bias);
    data._pad0 = 0.0f;
}

void LightingUBO::upload() {
    if (!buffer || !device_)
        return;
    device_->upload_buffer(
        buffer, std::span<const uint8_t>(reinterpret_cast<const uint8_t *>(&data), sizeof(data)));
}

} // namespace termin
