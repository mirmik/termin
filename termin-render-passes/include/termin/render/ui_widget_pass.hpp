#pragma once

#include <memory>
#include <vector>

#include <termin/gui_native/native_document_painter.hpp>
#include "tc_inspect_cpp.hpp"
#include "termin/render/frame_pass.hpp"
#include "termin/render_passes/export.h"

namespace termin {

struct ExecuteContext;

TERMIN_RENDER_PASSES_API
std::vector<gui_native::UiDocumentSubmission>
collect_ui_document_submissions(
    const ExecuteContext& ctx,
    bool include_internal_entities);

class TERMIN_RENDER_PASSES_API UIWidgetPass : public CxxFramePass {
public:
    static void register_type();
    std::string input_res = "color+ui";
    std::string output_res = "color+widgets";
    std::string font_path;
    bool include_internal_entities = false;

    INSPECT_FIELD(UIWidgetPass, input_res, "Input Resource", "string")
    INSPECT_FIELD(UIWidgetPass, output_res, "Output Resource", "string")
    INSPECT_FIELD(UIWidgetPass, font_path, "Font Path", "string")
    INSPECT_FIELD(UIWidgetPass, include_internal_entities, "Include Internal Entities", "bool")
    INSPECT_TYPE_METADATA(UIWidgetPass, graph, make_pass_graph_metadata(
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}},
        {{"input_res", "output_res"}}
    ))

    UIWidgetPass(
        const std::string& input = "color+ui",
        const std::string& output = "color+widgets"
    );
    ~UIWidgetPass() override;

    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;
    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override;

    void execute(ExecuteContext& ctx) override;
    void destroy() override;

private:
    void configure_font();

    std::unique_ptr<gui_native::NativeDocumentPainter> painter_;
    std::string configured_font_path_;
    bool font_configuration_attempted_ = false;
};

} // namespace termin
