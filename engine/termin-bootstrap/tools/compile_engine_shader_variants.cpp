#include <termin/bootstrap/bootstrap.hpp>
#include <termin/render/color_pass.hpp>
#include <termin/render/line_renderer.hpp>
#include <termin/tc_scene.hpp>
#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/shader_artifact_resolver.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

#include <cstdio>
#include <filesystem>
#include <string_view>
#include <vector>

namespace {

    bool compile_default_line(const termin::ShaderArtifactResolver& resolver, tgfx::ShaderArtifactTarget target) {
        auto scene = termin::TcSceneRef::create("Default Line Shader");
        if (!scene.valid()) {
            std::fprintf(stderr, "Cannot create the default line shader fixture\n");
            return false;
        }
        auto entity = scene.create_entity("Line");
        if (!entity.valid()) {
            std::fprintf(stderr, "Cannot create the line entity for shader planning\n");
            scene.destroy();
            return false;
        }
        auto* line = new termin::LineRenderer();
        line->set_segment({0.0, 0.0, 0.0}, {1.0, 0.0, 0.0});
        entity.add_component(line);

        termin::ColorPass pass;
        std::vector<termin::TcShader> variants;
        pass.collect_scene_shader_usages(scene.handle(), [&](termin::TcShader shader) {
            if (shader.variant_op() == TC_SHADER_VARIANT_LINE_TUBE) {
                variants.push_back(shader);
            }
        });
        scene.destroy();
        if (variants.size() != 1 || !variants.front().is_valid()) {
            std::fprintf(stderr, "ColorPass reported %zu default line shader variants, expected one valid variant\n",
                         variants.size());
            return false;
        }

        auto& variant = variants.front();
        std::vector<uint8_t> artifact;
        for (const auto stage : {tgfx::ShaderStage::Vertex, tgfx::ShaderStage::Fragment}) {
            if (!termin::tgfx2_load_or_compile_shader_artifact_for_target(resolver, variant.get(), target, stage, artifact)) {
                std::fprintf(stderr, "Cannot compile the default line variant %s for %s (stage %u)\n",
                             variant.uuid(), tgfx::shader_artifact_target_name(target), static_cast<unsigned>(stage));
                return false;
            }
        }
        return true;
    }

} // namespace

int main(int argc, char** argv) {
    if (argc != 5) {
        std::fprintf(stderr, "Usage: termin_compile_engine_shader_variants <vulkan|d3d11> <builtin-source-root> "
                             "<output-root> <termin_shaderc>\n");
        return 2;
    }
    const std::string_view backend = argv[1];
    tgfx::ShaderArtifactTarget target;
    if (backend == "vulkan") {
        target = tgfx::ShaderArtifactTarget::Vulkan;
    } else if (backend == "d3d11") {
        target = tgfx::ShaderArtifactTarget::D3D11;
    } else {
        std::fprintf(stderr, "Unsupported shader target: %s\n", argv[1]);
        return 2;
    }

    const auto cache_root = std::filesystem::path(argv[3]) / "compiler-cache";
    const termin::ShaderArtifactResolver resolver(argv[3], cache_root.string(), argv[4], true);
    tgfx::set_builtin_shader_root(argv[2]);
    termin::bootstrap::bootstrap_runtime();
    const bool compiled = compile_default_line(resolver, target);
    termin::bootstrap::shutdown_runtime();
    return compiled ? 0 : 1;
}
