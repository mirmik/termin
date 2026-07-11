#include "default_pipeline_factory.hpp"

#include <initializer_list>
#include <string>
#include <utility>

extern "C" {
#include <tcbase/tc_log.h>
#include "inspect/tc_inspect_pass_adapter.h"
#include "render/tc_pass.h"
#include "render/tc_pipeline.h"
}

namespace termin::rendering_manager_detail {

static tc_pass* create_and_configure_pass(
    const char* type_name,
    const char* pass_name,
    std::initializer_list<std::pair<const char*, const char*>> fields
) {
    if (!tc_pass_registry_has(type_name)) {
        tc_log(TC_LOG_WARN, "[make_default_pipeline] Pass type is not registered: '%s'", type_name);
        return nullptr;
    }
    tc_pass* pass = tc_pass_registry_create(type_name);
    if (!pass) {
        tc_log(TC_LOG_WARN, "[make_default_pipeline] Failed to create pass '%s'", type_name);
        return nullptr;
    }
    tc_pass_set_name(pass, pass_name);
    for (auto& [field, value] : fields) {
        tc_value v = tc_value_string(value);
        tc_pass_inspect_set(pass, field, v, nullptr);
        tc_value_free(&v);
    }
    return pass;
}

static void adopt_default_pass(tc_pipeline_handle pipeline, tc_pass* pass) {
    if (!tc_pipeline_adopt_pass(pipeline, pass, pass ? pass->deleter : nullptr)) {
        tc_log(TC_LOG_ERROR, "[make_default_pipeline] Failed to adopt configured pass");
        tc_pass_delete_unowned(pass);
    }
}

tc_pipeline_handle make_default_pipeline() {
    tc_pipeline_handle ph = tc_pipeline_create("Default");
    RenderPipeline pipeline(ph);

    if (tc_pass* p = create_and_configure_pass("ShadowPass", "Shadow", {
            {"output_res", "shadow_maps"}
        })) {
        adopt_default_pass(ph, p);
    }

    if (tc_pass* p = create_and_configure_pass("SkyBoxPass", "Skybox", {
            {"input_res", "empty"},
            {"output_res", "skybox"}
        })) {
        adopt_default_pass(ph, p);
    }

    if (tc_pass* p = create_and_configure_pass("ColorPass", "Color", {
            {"input_res", "skybox"},
            {"output_res", "color_opaque"},
            {"shadow_res", "shadow_maps"},
            {"phase_mark", "opaque"}
        })) {
        adopt_default_pass(ph, p);
    }

    if (tc_pass* p = create_and_configure_pass("ColorPass", "Transparent", {
            {"input_res", "color_opaque"},
            {"output_res", "color"},
            {"shadow_res", ""},
            {"phase_mark", "transparent"},
            {"sort_mode", "far_to_near"}
        })) {
        adopt_default_pass(ph, p);
    }

    if (tc_pass* p = create_and_configure_pass("ResolvePass", "Resolve", {
        {"input_res", "color"},
        {"output_res", "color_resolved"},
    })) {
        adopt_default_pass(ph, p);
    }

    if (tc_pass* p = create_and_configure_pass("BloomPass", "Bloom", {
        {"input_res", "color_resolved"},
        {"output_res", "color_bloom"},
    })) {
        adopt_default_pass(ph, p);
    }

    if (tc_pass* p = create_and_configure_pass("UIWidgetPass", "UIWidgets", {
            {"input_res", "color_bloom"},
            {"output_res", "color+widgets"}
        })) {
        adopt_default_pass(ph, p);
    }

    if (tc_pass* p = create_and_configure_pass("PresentToScreenPass", "Present", {
            {"input_res", "color+widgets"}
        })) {
        adopt_default_pass(ph, p);
    }

    const char* color_resources[] = {
        "empty",
        "skybox",
        "color_opaque",
        "color",
        "color_resolved",
        "color_bloom",
        "color+widgets",
    };
    for (const char* resource : color_resources) {
        ResourceSpec spec;
        spec.resource = resource;
        spec.format = "render_target";
        if (std::string(resource) == "empty" ||
            std::string(resource) == "skybox" ||
            std::string(resource) == "color_opaque" ||
            std::string(resource) == "color") {
            spec.samples = 4;
        }
        pipeline.add_spec(spec);
    }

    return ph;
}

} // namespace termin::rendering_manager_detail
