// All passes share placement, scale and motion, including shadow geometry.
import termin_foliage_material_transform;

float3 termin_shadow_foliage_world_position(float3 position, uint instance_id) {
    return termin_foliage_world_position(position, instance_id);
}
