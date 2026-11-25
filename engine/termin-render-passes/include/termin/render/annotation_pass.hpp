#pragma once

#include <tc_inspect_cpp.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render_passes/export.h>
#include <termin_visual_scene/tc_visual_scene3d.h>
#include <tgfx2/immediate_renderer.hpp>

namespace termin {
    // Painter-ordered VisualScene3D annotations over an engine camera's color output.
    class TERMIN_RENDER_PASSES_API AnnotationPass : public CxxFramePass {
    public:
        AnnotationPass(const std::string& input = "color", const std::string& output = "annotated");
        // Borrows a generation-checked scene handle. The host owns both the
        // scene and the conversion from logical DIPs to render-target pixels.
        bool set_scene(uint32_t index, uint32_t generation, float pixels_per_dip);

        std::string input_res, output_res;
        std::set<const char*> compute_reads() const override;
        std::set<const char*> compute_writes() const override;
        std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override;
        void execute(ExecuteContext& ctx) override;
        static void register_type();
        INSPECT_FIELD(AnnotationPass, input_res, "Input Resource", "string")
        INSPECT_FIELD(AnnotationPass, output_res, "Output Resource", "string")
        INSPECT_TYPE_METADATA(AnnotationPass,
                              graph,
                              make_pass_graph_metadata({{"input_res", "fbo"}},
                                                       {{"output_res", "fbo"}},
                                                       {{"input_res", "output_res"}}))

    private:
        tc_visual_scene3d_handle scene_ = tc_visual_scene3d_handle_invalid();
        float pixels_per_dip_ = 1;
        ImmediateRenderer renderer_;
    };
} // namespace termin
