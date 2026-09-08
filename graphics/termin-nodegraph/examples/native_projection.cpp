#include <termin/nodegraph/view.hpp>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <termin/gui_native/offscreen_composition.hpp>
#include <termin/gui_native/scene_view.hpp>
#include <termin_visual_scene/scene2d.hpp>
#include <tgfx2/device_factory.hpp>

namespace ng = termin::nodegraph;

namespace {

    tgfx::BackendType offscreen_backend() {
        if (tgfx::backend_is_compiled(tgfx::BackendType::Vulkan))
            return tgfx::BackendType::Vulkan;
        if (tgfx::backend_is_compiled(tgfx::BackendType::D3D11))
            return tgfx::BackendType::D3D11;
        return tgfx::BackendType::Null;
    }

    ng::Graph make_graph() {
        ng::Graph graph;

        ng::GroupDescriptor group;
        group.id = "processing";
        group.title = "Processing";
        group.x = -230.0f;
        group.y = -120.0f;
        group.width = 560.0f;
        group.height = 280.0f;
        if (!graph.create_group(std::move(group)))
            throw std::runtime_error("failed to create example group");

        ng::NodeDescriptor source;
        source.id = "source";
        source.kind = "producer";
        source.title = "Source";
        source.x = -180.0f;
        source.y = -55.0f;
        source.outputs.push_back({"samples", "signal", true});
        source.params["enabled"] = true;
        source.data["param_specs"]["enabled"]["kind"] = "bool";
        source.data["param_specs"]["enabled"]["label"] = "Enabled";
        const auto source_handle = graph.create_node(std::move(source));

        ng::NodeDescriptor filter;
        filter.id = "filter";
        filter.kind = "transform";
        filter.title = "Filter";
        filter.x = 80.0f;
        filter.y = 15.0f;
        filter.inputs.push_back({"input", "signal", false});
        filter.outputs.push_back({"output", "signal", true});
        filter.params["gain"] = 0.75;
        filter.data["param_specs"]["gain"]["kind"] = "float";
        filter.data["param_specs"]["gain"]["label"] = "Gain";
        filter.data["param_specs"]["gain"]["min"] = 0.0;
        filter.data["param_specs"]["gain"]["max"] = 2.0;
        filter.data["param_specs"]["gain"]["step"] = 0.05;
        const auto filter_handle = graph.create_node(std::move(filter));

        if (!source_handle || !filter_handle)
            throw std::runtime_error("failed to create example nodes");
        if (!graph.connect({source_handle.value, "samples", filter_handle.value, "input", "source-filter"}))
            throw std::runtime_error("failed to connect example nodes");
        return graph;
    }

    bool different_from_background(const std::vector<float>& pixels, float background) {
        std::size_t covered = 0;
        for (std::size_t offset = 0; offset + 3 < pixels.size(); offset += 4) {
            const float delta = std::max({std::fabs(pixels[offset] - background),
                                          std::fabs(pixels[offset + 1] - background),
                                          std::fabs(pixels[offset + 2] - background)});
            if (delta > 0.025f)
                ++covered;
        }
        return covered > 4000;
    }

    unsigned char linear_to_srgb8(float value) {
        value = std::clamp(value, 0.0f, 1.0f);
        const float srgb = value <= 0.0031308f ? value * 12.92f : 1.055f * std::pow(value, 1.0f / 2.4f) - 0.055f;
        return static_cast<unsigned char>(std::lround(std::clamp(srgb, 0.0f, 1.0f) * 255.0f));
    }

    void write_ppm(const std::string& path, const std::vector<float>& pixels, int width, int height) {
        std::ofstream output(path, std::ios::binary);
        if (!output)
            throw std::runtime_error("failed to open output image: " + path);
        output << "P6\n" << width << ' ' << height << "\n255\n";
        for (std::size_t offset = 0; offset + 3 < pixels.size(); offset += 4) {
            const unsigned char rgb[] = {
                linear_to_srgb8(pixels[offset]),
                linear_to_srgb8(pixels[offset + 1]),
                linear_to_srgb8(pixels[offset + 2]),
            };
            output.write(reinterpret_cast<const char*>(rgb), sizeof(rgb));
        }
        if (!output)
            throw std::runtime_error("failed to write output image: " + path);
    }

} // namespace

int main(int argc, char** argv) {
    std::string output_path;
    for (int index = 1; index < argc; ++index) {
        const std::string_view argument = argv[index];
        if (argument == "--output" && index + 1 < argc) {
            output_path = argv[++index];
        } else if (argument != "--verify") {
            std::fprintf(stderr, "usage: %s [--verify] [--output FILE.ppm]\n", argv[0]);
            return EXIT_FAILURE;
        }
    }

    const tgfx::BackendType backend = offscreen_backend();
    if (backend == tgfx::BackendType::Null) {
        std::printf("nodegraph projection example skipped: no Vulkan or D3D11 backend\n");
        return 77;
    }

    try {
        termin::gui_native::OffscreenGuiCompositionConfig config;
        config.width = 640;
        config.height = 400;
        config.backend = backend;
        config.continuous_rendering = false;
        config.renderer.font_path = TERMIN_NODEGRAPH_EXAMPLE_FONT;
        config.shader_compiler_path = TERMIN_NODEGRAPH_EXAMPLE_SHADERC;
        termin::gui_native::OffscreenGuiComposition composition(std::move(config));

        ng::Graph graph = make_graph();
        ng::NodeGraphView nodegraph(composition.document(), &graph);
        nodegraph.set_request_render_callback([&composition] { composition.request_repaint(); });
        if (!composition.document().add_root(*nodegraph.scene_view()))
            throw std::runtime_error("failed to attach nodegraph root widget");
        nodegraph.scene_view()->set_show_grid(false);
        nodegraph.scene_view()->set_offset({320.0f, 195.0f});
        nodegraph.scene_view()->set_scene_colors(
            {0.09f, 0.10f, 0.12f, 1.0f}, {0.15f, 0.16f, 0.20f, 1.0f}, {0.24f, 0.27f, 0.34f, 1.0f});

        if (!composition.render_frame())
            throw std::runtime_error("offscreen composition did not render");
        const std::vector<float> first = composition.read_frame_rgba_float();
        if (first.size() != 640u * 400u * 4u || !different_from_background(first, 0.09f))
            throw std::runtime_error("projected graph is not visible in offscreen output");

        nodegraph.scene_view()->invalidate_scene();
        if (!composition.render_frame())
            throw std::runtime_error("offscreen composition did not render a stable second frame");
        const std::vector<float> second = composition.read_frame_rgba_float();
        if (second.size() != first.size())
            throw std::runtime_error("offscreen output size changed between identical frames");
        float maximum_delta = 0.0f;
        for (std::size_t index = 0; index < first.size(); ++index)
            maximum_delta = std::max(maximum_delta, std::fabs(first[index] - second[index]));
        if (maximum_delta > 0.0005f)
            throw std::runtime_error("offscreen projection changed between identical frames");

        if (!output_path.empty())
            write_ppm(output_path, second, 640, 400);
        nodegraph.close();
        composition.close();
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "nodegraph projection example failed: %s\n", error.what());
        return EXIT_FAILURE;
    }
}
