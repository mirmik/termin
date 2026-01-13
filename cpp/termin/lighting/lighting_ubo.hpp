#pragma once

#include <cstdint>
#include <cstring>
#include <vector>

#include "termin/lighting/light.hpp"
#include "termin/lighting/shadow.hpp"
#include "termin/render/handles.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/geom/vec3.hpp"

namespace termin {

// Binding point for lighting UBO (must match GLSL)
constexpr int LIGHTING_UBO_BINDING = 0;

// Maximum lights (must match GLSL)
constexpr int UBO_MAX_LIGHTS = 8;

// Light data in std140 layout.
// Each field is packed into vec4s for proper alignment.
// Total: 80 bytes per light (5 x vec4)
struct alignas(16) LightDataStd140 {
    // vec4: color.rgb + intensity
    float color[3];
    float intensity;

    // vec4: direction.xyz + range
    float direction[3];
    float range;

    // vec4: position.xyz + type (as float, cast to int in shader)
    float position[3];
    float type;

    // vec4: attenuation.xyz + inner_angle
    float attenuation[3];
    float inner_angle;

    // vec4: outer_angle + cascade_count + cascade_blend + blend_distance
    float outer_angle;
    float cascade_count;
    float cascade_blend;
    float blend_distance;
};

static_assert(sizeof(LightDataStd140) == 80, "LightDataStd140 must be 80 bytes");

// Full lighting UBO data in std140 layout.
// Total: 688 bytes (640 + 16 + 16 + 16)
struct alignas(16) LightingUBOData {
    // 8 lights x 80 bytes = 640 bytes
    LightDataStd140 lights[UBO_MAX_LIGHTS];

    // vec4: ambient.rgb + ambient_intensity (16 bytes)
    float ambient_color[3];
    float ambient_intensity;

    // vec4: camera_position.xyz + light_count (16 bytes)
    float camera_position[3];
    float light_count;

    // vec4: shadow settings (16 bytes)
    float shadow_method;
    float shadow_softness;
    float shadow_bias;
    float _pad0;
};

static_assert(sizeof(LightingUBOData) == 688, "LightingUBOData must be 688 bytes");

// Helper class to manage lighting UBO
class LightingUBO {
public:
    LightingUBOData data;
    UniformBufferHandlePtr buffer;

    LightingUBO() {
        std::memset(&data, 0, sizeof(data));
    }

    // Create the GPU buffer
    void create(GraphicsBackend* graphics) {
        if (!buffer) {
            buffer = graphics->create_uniform_buffer(sizeof(LightingUBOData));
        }
    }

    // Update UBO from lights vector
    void update_from_lights(
        const std::vector<Light>& lights,
        const Vec3& ambient_color,
        float ambient_intensity,
        const Vec3& camera_position,
        const ShadowSettings& shadow_settings
    ) {
        int count = static_cast<int>(std::min(lights.size(), static_cast<size_t>(UBO_MAX_LIGHTS)));

        for (int i = 0; i < count; ++i) {
            const Light& light = lights[i];
            LightDataStd140& ld = data.lights[i];

            ld.color[0] = static_cast<float>(light.color.x);
            ld.color[1] = static_cast<float>(light.color.y);
            ld.color[2] = static_cast<float>(light.color.z);
            ld.intensity = static_cast<float>(light.intensity);

            ld.direction[0] = static_cast<float>(light.direction.x);
            ld.direction[1] = static_cast<float>(light.direction.y);
            ld.direction[2] = static_cast<float>(light.direction.z);
            ld.range = light.range.has_value() ? static_cast<float>(light.range.value()) : 1e9f;

            ld.position[0] = static_cast<float>(light.position.x);
            ld.position[1] = static_cast<float>(light.position.y);
            ld.position[2] = static_cast<float>(light.position.z);

            // Type as float (0=DIR, 1=POINT, 2=SPOT)
            switch (light.type) {
                case LightType::Directional: ld.type = 0.0f; break;
                case LightType::Point: ld.type = 1.0f; break;
                case LightType::Spot: ld.type = 2.0f; break;
            }

            ld.attenuation[0] = static_cast<float>(light.attenuation.constant);
            ld.attenuation[1] = static_cast<float>(light.attenuation.linear);
            ld.attenuation[2] = static_cast<float>(light.attenuation.quadratic);
            ld.inner_angle = static_cast<float>(light.inner_angle);

            ld.outer_angle = static_cast<float>(light.outer_angle);
            ld.cascade_count = static_cast<float>(light.shadows.cascade_count);
            ld.cascade_blend = light.shadows.cascade_blend ? 1.0f : 0.0f;
            ld.blend_distance = light.shadows.blend_distance;
        }

        // Zero out unused light slots
        for (int i = count; i < UBO_MAX_LIGHTS; ++i) {
            std::memset(&data.lights[i], 0, sizeof(LightDataStd140));
        }

        // Ambient
        data.ambient_color[0] = static_cast<float>(ambient_color.x);
        data.ambient_color[1] = static_cast<float>(ambient_color.y);
        data.ambient_color[2] = static_cast<float>(ambient_color.z);
        data.ambient_intensity = ambient_intensity;

        // Camera position
        data.camera_position[0] = static_cast<float>(camera_position.x);
        data.camera_position[1] = static_cast<float>(camera_position.y);
        data.camera_position[2] = static_cast<float>(camera_position.z);
        data.light_count = static_cast<float>(count);

        // Shadow settings
        data.shadow_method = static_cast<float>(shadow_settings.method);
        data.shadow_softness = static_cast<float>(shadow_settings.softness);
        data.shadow_bias = static_cast<float>(shadow_settings.bias);
        data._pad0 = 0.0f;
    }

    // Upload data to GPU and bind
    void upload_and_bind() {
        if (buffer) {
            buffer->update(&data, sizeof(data));
            buffer->bind(LIGHTING_UBO_BINDING);
        }
    }

    // Just bind (data already uploaded)
    void bind() {
        if (buffer) {
            buffer->bind(LIGHTING_UBO_BINDING);
        }
    }

    void unbind() {
        if (buffer) {
            buffer->unbind();
        }
    }
};

} // namespace termin
