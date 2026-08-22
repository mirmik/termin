#include <resources/tc_animation.h>
#include <resources/tc_skeleton.h>
#include <resources/tc_skeleton_registry.h>
#include <termin/glb/native_backend.h>
#include <termin/materials/shader_parser.hpp>
#include <termin/skeleton/skeleton_instance.hpp>
#include <termin/skeleton/tc_skeleton_handle.hpp>

#include <cmath>
#include <iostream>
#include <string_view>

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "expected generated GLB path\n";
        return 1;
    }

    const auto parsed =
        termin::parse_shader_text("@program installed\n@language slang\n@property Float roughness = 0.5\n"
                                  "@phase opaque\n@stage vertex vs_main\nfloat4 vs_main(float3 p : POSITION) : "
                                  "SV_Position { return float4(p, 1); }\n@endstage\n@endphase\n");
    if (parsed.program != "installed" || parsed.material_properties.size() != 1) {
        std::cerr << "installed material parser lost @property metadata\n";
        return 2;
    }

    termin::TcSkeleton skeleton = termin::TcSkeleton::create("installed-consumer");
    if (!skeleton.is_valid())
        return 3;
    const tc_skeleton_bone_desc bones[2] = {
        {"Root", -1, tc_mat44_identity(), tc_vec3_zero(), tc_quat_identity(), tc_vec3_one()},
        {"Child", 0, tc_mat44_identity(), {0.0, 1.0, 0.0}, tc_quat_identity(), tc_vec3_one()},
    };
    if (!skeleton.replace_bones(bones, 2))
        return 3;
    termin::SkeletonInstance pose(skeleton);
    if (pose.bone_count() != 2 || std::abs(pose.get_bone_world_matrix(1)(3, 1) - 1.0) > 1e-9)
        return 3;

    tc_keyframe_vec3 keys[2] = {{0.0, {0.0, 0.0, 0.0}}, {1.0, {0.0, 1.0, 0.0}}};
    tc_animation_channel channel{};
    tc_animation_channel_init(&channel);
    channel.translation_keys = keys;
    channel.translation_count = 2;
    tc_channel_sample sample{};
    if (!tc_animation_channel_sample(&channel, 0.5, &sample) || !sample.has_translation ||
        std::abs(sample.translation.y - 0.5) > 1e-9)
        return 4;
    channel.translation_keys = nullptr;

    termin_glb_error error{};
    termin_glb_document* document = termin_glb_document_open(argv[1], &error);
    if (!document) {
        std::cerr << "GLB open failed: " << error.message << "\n";
        return 5;
    }
    const bool closure_ok = termin_glb_document_mesh_count(document) == 1 &&
                            termin_glb_document_skin_count(document) == 1 &&
                            termin_glb_document_animation_count(document) == 1;
    termin_glb_document_close(document);
    if (!closure_ok) {
        std::cerr << "generated GLB did not expose mesh+skin+animation\n";
        return 6;
    }
    return 0;
}
