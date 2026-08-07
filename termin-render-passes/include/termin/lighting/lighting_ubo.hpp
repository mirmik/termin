#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <span>
#include <vector>

#include "termin/lighting/shadow.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/handles.hpp"
#include "tgfx2/i_render_device.hpp"
#include <termin/geom/vec3.hpp>
#include <termin/lighting/light.hpp>
#include <termin/render_passes/export.h>

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
        Vec3f color;
        float intensity;

        // vec4: direction.xyz + range
        Vec3f direction;
        float range;

        // vec4: position.xyz + type (as float, cast to int in shader)
        Vec3f position;
        float type;

        // vec4: attenuation.xyz + inner_angle
        Vec3f attenuation;
        float inner_angle;

        // vec4: outer_angle + cascade_count + cascade_blend + blend_distance
        float outer_angle;
        float cascade_count;
        float cascade_blend;
        float blend_distance;
    };

    static_assert(sizeof(LightDataStd140) == 80, "LightDataStd140 must be 80 bytes");
    static_assert(offsetof(LightDataStd140, color) == 0);
    static_assert(offsetof(LightDataStd140, intensity) == 12);
    static_assert(offsetof(LightDataStd140, direction) == 16);
    static_assert(offsetof(LightDataStd140, range) == 28);
    static_assert(offsetof(LightDataStd140, position) == 32);
    static_assert(offsetof(LightDataStd140, type) == 44);
    static_assert(offsetof(LightDataStd140, attenuation) == 48);
    static_assert(offsetof(LightDataStd140, inner_angle) == 60);

    // Full lighting UBO data in std140 layout.
    // Total: 688 bytes (640 + 16 + 16 + 16)
    struct alignas(16) LightingUBOData {
        // 8 lights x 80 bytes = 640 bytes
        LightDataStd140 lights[UBO_MAX_LIGHTS];

        // vec4: ambient.rgb + ambient_intensity (16 bytes)
        Vec3f ambient_color;
        float ambient_intensity;

        // vec4: camera_position.xyz + light_count (16 bytes)
        Vec3f camera_position;
        float light_count;

        // vec4: shadow settings (16 bytes)
        float shadow_method;
        float shadow_softness;
        float shadow_bias;
        float _pad0;
    };

    static_assert(sizeof(LightingUBOData) == 688, "LightingUBOData must be 688 bytes");
    static_assert(offsetof(LightingUBOData, ambient_color) == 640);
    static_assert(offsetof(LightingUBOData, ambient_intensity) == 652);
    static_assert(offsetof(LightingUBOData, camera_position) == 656);
    static_assert(offsetof(LightingUBOData, light_count) == 668);

    // Helper class to manage lighting UBO
    class TERMIN_RENDER_PASSES_API LightingUBO {
    public:
        LightingUBOData data;
        tgfx::BufferHandle buffer;

    private:
        tgfx::IRenderDevice* device_ = nullptr;

    public:
        LightingUBO();

        // Create the GPU buffer through the tgfx2 device. Idempotent —
        // calling twice on the same device is a no-op. If the device
        // pointer changes between frames the buffer is recreated; this
        // happens when the RenderEngine's tgfx2 stack is rebuilt
        // (resolution change, context reset, ...).
        void create(tgfx::IRenderDevice& device);

        void destroy();

        ~LightingUBO();

        LightingUBO(const LightingUBO&) = delete;
        LightingUBO& operator=(const LightingUBO&) = delete;

        // Update UBO from a non-owning lights view.
        void update_from_lights(std::span<const Light> lights,
                                const Vec3& ambient_color,
                                float ambient_intensity,
                                const Vec3& camera_position,
                                const ShadowSettings& shadow_settings);

        // Upload data to GPU (buffer must be create()'d first).
        void upload();
    };

} // namespace termin
