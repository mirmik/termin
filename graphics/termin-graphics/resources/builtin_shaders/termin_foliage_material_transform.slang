// Instanced foliage placement as a reusable material transform provider.

import termin_prelude;
import termin_vertex_transform;

struct FoliagePushData {
    column_major float4x4 u_position_model;
    column_major float4x4 u_vector_model;
    float4 wind; // world direction XY, amplitude, explicit time phase
    float4 motion; // spatial frequency, prototype height, interaction strength, reserved
    float4 interaction; // world sphere center XYZ and radius
};

[[TerminScope("draw")]]
ConstantBuffer<FoliagePushData> foliage_draw;

struct FoliageInstance {
    float3 position;
    float yaw;
    float3 normal;
    float seed;
    float scale;
    float padding0;
    float padding1;
    float padding2;
};

[[TerminScope("draw")]]
StructuredBuffer<FoliageInstance> foliage_instances;

TerminWorldVertex termin_foliage_material_world_vertex(
    float3 position,
    float3 normal,
    float2 uv,
    uint instance_id
) {
    FoliageInstance instance = foliage_instances[instance_id];

    float3 up = normalize(instance.normal);
    float3 helper = abs(up.z) > 0.85
        ? float3(0.0, 1.0, 0.0)
        : float3(0.0, 0.0, 1.0);
    float3 right = normalize(cross(helper, up));
    float3 forward = cross(up, right);

    float c = cos(instance.yaw);
    float s = sin(instance.yaw);
    float3 yaw_right = right * c + forward * s;
    float3 yaw_forward = -right * s + forward * c;
    float3 local_offset =
        (yaw_right * position.x + yaw_forward * position.y + up * position.z) * instance.scale;

    float3 source_normal = length(normal) > 0.0001
        ? normalize(normal)
        : float3(0.0, 0.0, 1.0);
    float3 local_normal = normalize(
        yaw_right * source_normal.x +
        yaw_forward * source_normal.y +
        up * source_normal.z);

    TerminWorldVertex output;
    float3 root = mul(foliage_draw.u_position_model, float4(instance.position, 1.0)).xyz;
    float3 world_up = normalize(mul(foliage_draw.u_vector_model, float4(up, 0.0)).xyz);
    float phase = dot(root.xy, foliage_draw.wind.xy) * foliage_draw.motion.x;
    float wave = 0.8 * sin(phase + foliage_draw.wind.w) +
                 0.2 * sin(phase * 1.7 + foliage_draw.wind.w + instance.seed * 0.618034);
    float3 bend = float3(foliage_draw.wind.xy, 0.0) * foliage_draw.wind.z * wave;
    float3 away = root - foliage_draw.interaction.xyz;
    float distance_to_center = length(away);
    float influence = saturate(1.0 - distance_to_center / max(foliage_draw.interaction.w, 0.0001));
    influence = influence * influence * (3.0 - 2.0 * influence);
    if (foliage_draw.interaction.w > 0.0 && distance_to_center > 0.0001) {
        bend += away / distance_to_center * influence * foliage_draw.motion.z;
    }
    // Tangent-plane shear has an invertible normal transform, also on slopes.
    bend -= world_up * dot(bend, world_up);
    float height = saturate(position.z / foliage_draw.motion.y);
    float weight = height * height;
    output.position = root + mul(foliage_draw.u_vector_model, float4(local_offset, 0.0)).xyz + bend * weight;
    output.normal = normalize(
        mul(foliage_draw.u_vector_model, float4(local_normal, 0.0)).xyz);
    float derivative = position.z > 0.0 && position.z < foliage_draw.motion.y
        ? 2.0 * height / foliage_draw.motion.y : 0.0;
    if (abs(instance.scale) > 0.0001) {
        output.normal = normalize(output.normal - world_up *
            dot(output.normal, bend) * derivative / instance.scale);
    }
    output.uv = uv;
    output.tangent = float4(0.0, 0.0, 0.0, 0.0);
    return output;
}

float3 termin_foliage_world_position(
    float3 position,
    uint instance_id
) {
    return termin_foliage_material_world_vertex(
        position,
        float3(0.0, 0.0, 1.0),
        float2(0.0, 0.0),
        instance_id).position;
}

TerminWorldPositionNormal termin_foliage_world_position_normal(
    float3 position,
    float3 normal,
    uint instance_id
) {
    TerminWorldVertex world = termin_foliage_material_world_vertex(
        position,
        normal,
        float2(0.0, 0.0),
        instance_id);
    TerminWorldPositionNormal output;
    output.position = world.position;
    output.normal = world.normal;
    return output;
}
