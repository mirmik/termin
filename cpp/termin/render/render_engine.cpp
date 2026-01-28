#include "render_engine.hpp"
#include "tc_log.hpp"
#include "tc_profiler.h"
#include "termin/camera/camera_component.hpp"

extern "C" {
#include "render/tc_frame_graph.h"
#include "render/tc_pass.h"
#include "tc_scene.h"
}

namespace termin {

RenderEngine::RenderEngine(GraphicsBackend* graphics)
    : graphics(graphics)
{
}

void RenderEngine::render_to_screen(
    RenderPipeline* pipeline,
    int width,
    int height,
    void* scene,
    CameraComponent* camera
) {
    // Validate inputs before passing to render_view_to_fbo
    if (!pipeline) {
        tc::Log::error("[render_to_screen] pipeline is NULL");
        return;
    }
    if (!scene) {
        tc::Log::error("[render_to_screen] scene is NULL");
        return;
    }
    if (!camera) {
        tc::Log::error("[render_to_screen] camera is NULL");
        return;
    }
    if (!camera->entity().valid()) {
        tc::Log::error("[render_to_screen] camera->entity is invalid");
        return;
    }

    // Simplified render to screen (default framebuffer)
    std::vector<Light> empty_lights;
    render_view_to_fbo(
        pipeline,
        nullptr,  // null = default framebuffer
        width,
        height,
        static_cast<tc_scene*>(scene),
        camera,
        nullptr,  // no viewport
        empty_lights,
        0xFFFFFFFFFFFFFFFFULL
    );
}

void RenderEngine::present_to_screen(
    RenderPipeline* pipeline,
    int width,
    int height,
    const std::string& resource_name
) {
    if (!pipeline || !graphics) {
        tc::Log::warn("[present_to_screen] pipeline=%p graphics=%p", pipeline, graphics);
        return;
    }

    // Get FBO from pipeline's pool
    FramebufferHandle* src_fbo = pipeline->fbo_pool().get(resource_name);
    if (!src_fbo) {
        tc::Log::warn("[present_to_screen] FBO '%s' not found in pipeline. Available FBOs:", resource_name.c_str());
        // List available FBOs
        auto& pool = pipeline->fbo_pool();
        for (const auto& key : pool.keys()) {
            auto* fbo = pool.get(key);
            tc::Log::warn("  - '%s': %p", key.c_str(), fbo);
        }
        return;
    }

    tc::Log::info("[present_to_screen] Blitting '%s' (%dx%d) to screen (%dx%d)", 
        resource_name.c_str(), src_fbo->get_width(), src_fbo->get_height(), width, height);

    // Blit to default framebuffer (screen)
    graphics->blit_framebuffer(
        src_fbo,
        nullptr,  // dst = default framebuffer
        0, 0, src_fbo->get_width(), src_fbo->get_height(),
        0, 0, width, height,
        true,   // blit color
        false   // don't blit depth
    );
}

void RenderEngine::render_view_to_fbo(
    RenderPipeline* pipeline,
    FramebufferHandle* target_fbo,
    int width,
    int height,
    tc_scene* scene,
    CameraComponent* camera,
    tc_viewport* viewport,
    const std::vector<Light>& lights,
    uint64_t layer_mask
) {
    if (!pipeline) {
        tc::Log::error("RenderEngine::render_view_to_fbo: pipeline is null");
        return;
    }
    tc_pipeline* pp = pipeline->ptr();
    if (!pp) {
        tc::Log::error("RenderEngine::render_view_to_fbo: pipeline->ptr() is null");
        return;
    }
    if (!graphics) {
        tc::Log::error("RenderEngine::render_view_to_fbo: graphics is null");
        return;
    }

    // Build frame graph
    tc_frame_graph* fg = tc_frame_graph_build(pipeline->ptr());
    if (!fg) {
        tc::Log::error("RenderEngine::render_view_to_fbo: failed to build frame graph");
        return;
    }

    if (tc_frame_graph_get_error(fg) != TC_FG_OK) {
        tc::Log::error("RenderEngine::render_view_to_fbo: frame graph error: %s",
                       tc_frame_graph_get_error_message(fg));
        tc_frame_graph_destroy(fg);
        return;
    }

    // Collect resource specs from pipeline + passes
    auto specs = pipeline->collect_specs();

    // Build spec map - merge specs with same resource name
    std::unordered_map<std::string, ResourceSpec> spec_map;
    for (const auto& spec : specs) {
        auto it = spec_map.find(spec.resource);
        if (it == spec_map.end()) {
            spec_map[spec.resource] = spec;
        } else {
            ResourceSpec& existing = it->second;
            if (spec.samples > 1 && existing.samples == 1) {
                existing.samples = spec.samples;
            }
            if (spec.format && !existing.format) {
                existing.format = spec.format;
            }
            if (spec.clear_color && !existing.clear_color) {
                existing.clear_color = spec.clear_color;
            }
            if (spec.clear_depth && !existing.clear_depth) {
                existing.clear_depth = spec.clear_depth;
            }
        }
    }

    // Allocate resources based on canonical names from frame graph
    FBOMap resources;
    resources["OUTPUT"] = target_fbo;
    resources["DISPLAY"] = target_fbo;

    const char* canonical_names[256];
    size_t canon_count = tc_frame_graph_get_canonical_resources(fg, canonical_names, 256);

    for (size_t i = 0; i < canon_count; i++) {
        const char* canon = canonical_names[i];

        // Skip OUTPUT/DISPLAY
        if (strcmp(canon, "OUTPUT") == 0 || strcmp(canon, "DISPLAY") == 0) {
            const char* aliases[64];
            size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
            for (size_t j = 0; j < alias_count; j++) {
                resources[aliases[j]] = target_fbo;
            }
            continue;
        }

        // Find spec
        const ResourceSpec* spec = nullptr;
        auto it = spec_map.find(canon);
        if (it != spec_map.end()) {
            spec = &it->second;
        } else {
            const char* aliases[64];
            size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
            for (size_t j = 0; j < alias_count && !spec; j++) {
                auto ait = spec_map.find(aliases[j]);
                if (ait != spec_map.end()) {
                    spec = &ait->second;
                }
            }
        }

        // Determine resource type
        std::string resource_type = "fbo";
        if (spec && !spec->resource_type.empty()) {
            resource_type = spec->resource_type;
        }

        // Handle shadow_map_array resources
        if (resource_type == "shadow_map_array") {
            auto& shadow_array = pipeline->shadow_arrays()[canon];
            if (!shadow_array) {
                int resolution = 1024;
                if (spec && spec->size) {
                    resolution = spec->size->first;
                }
                shadow_array = std::make_unique<ShadowMapArrayResource>(resolution);
            }

            const char* aliases[64];
            size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
            for (size_t j = 0; j < alias_count; j++) {
                resources[aliases[j]] = shadow_array.get();
            }
            continue;
        }

        // Skip other non-FBO resources
        if (resource_type != "fbo") {
            const char* aliases[64];
            size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
            for (size_t j = 0; j < alias_count; j++) {
                resources[aliases[j]] = nullptr;
            }
            continue;
        }

        // Determine FBO parameters
        int fbo_width = width;
        int fbo_height = height;
        int samples = 1;
        std::string format;

        if (spec) {
            if (spec->size) {
                fbo_width = spec->size->first;
                fbo_height = spec->size->second;
            }
            samples = spec->samples > 0 ? spec->samples : 1;
            if (spec->format) format = *spec->format;
        }

        // Get or create FBO in pipeline's pool
        FBOPool& fbo_pool = pipeline->fbo_pool();
        FramebufferHandle* fbo = fbo_pool.ensure(graphics, canon, fbo_width, fbo_height, samples, format);

        // Set for all aliases and register aliases in pool
        const char* aliases[64];
        size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
        for (size_t j = 0; j < alias_count; j++) {
            resources[aliases[j]] = fbo;
            fbo_pool.add_alias(aliases[j], canon);
        }
    }

    // Clear resources according to specs
    for (const auto& spec : specs) {
        if (spec.resource_type != "fbo" && !spec.resource_type.empty()) {
            continue;
        }
        if (!spec.clear_color && !spec.clear_depth) {
            continue;
        }

        auto it = resources.find(spec.resource);
        if (it == resources.end() || it->second == nullptr) {
            continue;
        }

        FramebufferHandle* fbo = dynamic_cast<FramebufferHandle*>(it->second);
        if (!fbo) {
            continue;
        }

        graphics->bind_framebuffer(fbo);

        int fb_w = spec.size ? spec.size->first : width;
        int fb_h = spec.size ? spec.size->second : height;
        graphics->set_viewport(0, 0, fb_w, fb_h);

        if (spec.clear_color && spec.clear_depth) {
            const auto& cc = *spec.clear_color;
            graphics->clear_color_depth(
                static_cast<float>(cc[0]), static_cast<float>(cc[1]),
                static_cast<float>(cc[2]), static_cast<float>(cc[3])
            );
        } else if (spec.clear_color) {
            const auto& cc = *spec.clear_color;
            graphics->clear_color(
                static_cast<float>(cc[0]), static_cast<float>(cc[1]),
                static_cast<float>(cc[2]), static_cast<float>(cc[3])
            );
        } else if (spec.clear_depth) {
            graphics->clear_depth(*spec.clear_depth);
        }
    }

    // Execute passes in schedule order
    size_t schedule_count = tc_frame_graph_schedule_count(fg);

    tc_profiler_begin_section("Execute Passes");
    for (size_t i = 0; i < schedule_count; i++) {
        tc_pass* pass = tc_frame_graph_schedule_at(fg, i);
        if (!pass || !pass->enabled || pass->passthrough) {
            continue;
        }

        // Profile each pass by name
        const char* pass_name = pass->pass_name ? pass->pass_name : "UnnamedPass";
        tc_profiler_begin_section(pass_name);

        graphics->reset_state();

        // Build reads/writes FBO maps for this pass
        const char* reads[16];
        const char* writes[8];
        size_t read_count = tc_pass_get_reads(pass, reads, 16);
        size_t write_count = tc_pass_get_writes(pass, writes, 8);

        FBOMap pass_reads;
        FBOMap pass_writes;

        for (size_t j = 0; j < read_count; j++) {
            auto it = resources.find(reads[j]);
            pass_reads[reads[j]] = (it != resources.end()) ? it->second : nullptr;
        }
        for (size_t j = 0; j < write_count; j++) {
            auto it = resources.find(writes[j]);
            pass_writes[writes[j]] = (it != resources.end()) ? it->second : nullptr;
        }

        // Build ExecuteContext
        ExecuteContext ctx;
        ctx.graphics = graphics;
        ctx.reads_fbos = std::move(pass_reads);
        ctx.writes_fbos = std::move(pass_writes);
        ctx.rect = Rect4i{0, 0, width, height};
        ctx.scene = TcSceneRef(scene);
        ctx.viewport = viewport;
        ctx.camera = camera;
        ctx.lights = lights;
        ctx.layer_mask = layer_mask;

        // Execute pass via vtable
        tc_pass_execute(pass, &ctx);

        tc_profiler_end_section(); // pass_name
    }
    tc_profiler_end_section(); // Execute Passes

    tc_frame_graph_destroy(fg);
}

void RenderEngine::render_scene_pipeline_offscreen(
    RenderPipeline* pipeline,
    tc_scene* scene,
    const std::unordered_map<std::string, ViewportContext>& viewport_contexts,
    const std::vector<Light>& lights,
    const std::string& default_viewport
) {
    if (!pipeline) {
        tc::Log::error("RenderEngine::render_scene_pipeline_offscreen: pipeline is null");
        return;
    }
    if (!graphics) {
        tc::Log::error("RenderEngine::render_scene_pipeline_offscreen: graphics is null");
        return;
    }
    if (viewport_contexts.empty()) {
        tc::Log::error("RenderEngine::render_scene_pipeline_offscreen: no viewport contexts");
        return;
    }

    // Select default viewport
    std::string default_vp = default_viewport;
    if (default_vp.empty()) {
        default_vp = viewport_contexts.begin()->first;
    }

    auto default_it = viewport_contexts.find(default_vp);
    if (default_it == viewport_contexts.end()) {
        default_it = viewport_contexts.begin();
    }
    const ViewportContext& default_ctx = default_it->second;

    int default_width = default_ctx.rect.width;
    int default_height = default_ctx.rect.height;

    // Build frame graph
    tc_profiler_begin_section("Build Frame Graph");
    tc_frame_graph* fg = tc_frame_graph_build(pipeline->ptr());
    if (!fg) {
        tc_profiler_end_section();
        tc::Log::error("RenderEngine::render_scene_pipeline_offscreen: failed to build frame graph");
        return;
    }

    if (tc_frame_graph_get_error(fg) != TC_FG_OK) {
        tc::Log::error("RenderEngine::render_scene_pipeline_offscreen: frame graph error: %s",
                       tc_frame_graph_get_error_message(fg));
        tc_frame_graph_destroy(fg);
        tc_profiler_end_section();
        return;
    }
    tc_profiler_end_section();

    // Collect resource specs from pipeline + passes
    tc_profiler_begin_section("Collect Specs");
    auto specs = pipeline->collect_specs();

    // Build spec map - merge specs with same resource name
    // Pipeline specs come first and have priority for samples/format
    std::unordered_map<std::string, ResourceSpec> spec_map;
    for (const auto& spec : specs) {
        auto it = spec_map.find(spec.resource);
        if (it == spec_map.end()) {
            spec_map[spec.resource] = spec;
        } else {
            ResourceSpec& existing = it->second;
            if (spec.samples > 1 && existing.samples == 1) {
                existing.samples = spec.samples;
            }
            if (spec.format && !existing.format) {
                existing.format = spec.format;
            }
            if (spec.clear_color && !existing.clear_color) {
                existing.clear_color = spec.clear_color;
            }
            if (spec.clear_depth && !existing.clear_depth) {
                existing.clear_depth = spec.clear_depth;
            }
        }
    }
    tc_profiler_end_section();

    // Allocate resources based on canonical names from frame graph
    tc_profiler_begin_section("Allocate Resources");
    FBOMap resources;

    // Set OUTPUT/DISPLAY to default viewport's output_fbo
    resources["OUTPUT"] = default_ctx.output_fbo;
    resources["DISPLAY"] = default_ctx.output_fbo;

    const char* canonical_names[256];
    size_t canon_count = tc_frame_graph_get_canonical_resources(fg, canonical_names, 256);

    for (size_t i = 0; i < canon_count; i++) {
        const char* canon = canonical_names[i];

        // Skip OUTPUT/DISPLAY - handled per-pass based on viewport
        if (strcmp(canon, "OUTPUT") == 0 || strcmp(canon, "DISPLAY") == 0) {
            const char* aliases[64];
            size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
            for (size_t j = 0; j < alias_count; j++) {
                resources[aliases[j]] = default_ctx.output_fbo;
            }
            continue;
        }

        // Find spec
        const ResourceSpec* spec = nullptr;
        auto it = spec_map.find(canon);
        if (it != spec_map.end()) {
            spec = &it->second;
        } else {
            const char* aliases[64];
            size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
            for (size_t j = 0; j < alias_count && !spec; j++) {
                auto ait = spec_map.find(aliases[j]);
                if (ait != spec_map.end()) {
                    spec = &ait->second;
                }
            }
        }

        // Determine resource type
        std::string resource_type = "fbo";
        if (spec && !spec->resource_type.empty()) {
            resource_type = spec->resource_type;
        }

        // Handle shadow_map_array resources
        if (resource_type == "shadow_map_array") {
            // Get or create ShadowMapArrayResource
            auto& shadow_array = pipeline->shadow_arrays()[canon];
            if (!shadow_array) {
                int resolution = 1024;
                if (spec && spec->size) {
                    resolution = spec->size->first;
                }
                shadow_array = std::make_unique<ShadowMapArrayResource>(resolution);
            }

            // Set for all aliases
            const char* aliases[64];
            size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
            for (size_t j = 0; j < alias_count; j++) {
                resources[aliases[j]] = shadow_array.get();
            }
            continue;
        }

        // Skip other non-FBO resources
        if (resource_type != "fbo") {
            const char* aliases[64];
            size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
            for (size_t j = 0; j < alias_count; j++) {
                resources[aliases[j]] = nullptr;
            }
            continue;
        }

        // Determine FBO parameters
        int fbo_width = default_width;
        int fbo_height = default_height;
        int samples = 1;
        std::string format;

        if (spec) {
            if (spec->size) {
                fbo_width = spec->size->first;
                fbo_height = spec->size->second;
            }
            samples = spec->samples > 0 ? spec->samples : 1;
            if (spec->format) format = *spec->format;
        }

        // Get or create FBO in pipeline's pool
        FBOPool& fbo_pool = pipeline->fbo_pool();
        FramebufferHandle* fbo = fbo_pool.ensure(graphics, canon, fbo_width, fbo_height, samples, format);

        // Set for all aliases and register aliases in pool
        const char* aliases[64];
        size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
        for (size_t j = 0; j < alias_count; j++) {
            resources[aliases[j]] = fbo;
            fbo_pool.add_alias(aliases[j], canon);
        }
    }
    tc_profiler_end_section();

    // Clear resources according to specs
    tc_profiler_begin_section("Clear Resources");
    for (const auto& spec : specs) {
        if (spec.resource_type != "fbo" && !spec.resource_type.empty()) {
            continue;
        }
        if (!spec.clear_color && !spec.clear_depth) {
            continue;
        }

        auto it = resources.find(spec.resource);
        if (it == resources.end() || it->second == nullptr) {
            continue;
        }

        FramebufferHandle* fbo = dynamic_cast<FramebufferHandle*>(it->second);
        if (!fbo) continue;

        graphics->bind_framebuffer(fbo);

        int fb_w = spec.size ? spec.size->first : default_width;
        int fb_h = spec.size ? spec.size->second : default_height;
        graphics->set_viewport(0, 0, fb_w, fb_h);

        if (spec.clear_color && spec.clear_depth) {
            const auto& cc = *spec.clear_color;
            graphics->clear_color_depth(
                static_cast<float>(cc[0]), static_cast<float>(cc[1]),
                static_cast<float>(cc[2]), static_cast<float>(cc[3])
            );
        } else if (spec.clear_color) {
            const auto& cc = *spec.clear_color;
            graphics->clear_color(
                static_cast<float>(cc[0]), static_cast<float>(cc[1]),
                static_cast<float>(cc[2]), static_cast<float>(cc[3])
            );
        } else if (spec.clear_depth) {
            graphics->clear_depth(*spec.clear_depth);
        }
    }
    tc_profiler_end_section();

    // Execute passes in schedule order
    size_t schedule_count = tc_frame_graph_schedule_count(fg);

    tc_profiler_begin_section("Execute Passes");
    for (size_t i = 0; i < schedule_count; i++) {
        tc_pass* pass = tc_frame_graph_schedule_at(fg, i);
        if (!pass || !pass->enabled || pass->passthrough) {
            continue;
        }

        // Profile each pass by name
        const char* pass_name = pass->pass_name ? pass->pass_name : "UnnamedPass";
        tc_profiler_begin_section(pass_name);

        graphics->reset_state();

        // Determine viewport context for this pass
        std::string pass_viewport_name = default_vp;
        if (pass->viewport_name && pass->viewport_name[0] != '\0') {
            pass_viewport_name = pass->viewport_name;
        }

        auto vp_it = viewport_contexts.find(pass_viewport_name);
        if (vp_it == viewport_contexts.end()) {
            vp_it = default_it;
        }
        const ViewportContext& vp_ctx = vp_it->second;

        // Build reads/writes FBO maps for this pass
        const char* reads[16];
        const char* writes[8];
        size_t read_count = tc_pass_get_reads(pass, reads, 16);
        size_t write_count = tc_pass_get_writes(pass, writes, 8);

        FBOMap pass_reads;
        FBOMap pass_writes;

        for (size_t j = 0; j < read_count; j++) {
            auto it = resources.find(reads[j]);
            FrameGraphResource* res = (it != resources.end()) ? it->second : nullptr;
            pass_reads[reads[j]] = res;
        }

        for (size_t j = 0; j < write_count; j++) {
            const char* write_name = writes[j];
            // For OUTPUT/DISPLAY, use this viewport's output_fbo
            if (strcmp(write_name, "OUTPUT") == 0 || strcmp(write_name, "DISPLAY") == 0) {
                pass_writes[write_name] = vp_ctx.output_fbo;
            } else {
                auto it = resources.find(write_name);
                FrameGraphResource* res = (it != resources.end()) ? it->second : nullptr;
                pass_writes[write_name] = res;
            }
        }

        // Build ExecuteContext
        ExecuteContext ctx;
        ctx.graphics = graphics;
        ctx.reads_fbos = std::move(pass_reads);
        ctx.writes_fbos = std::move(pass_writes);
        ctx.rect = vp_ctx.rect;
        ctx.scene = TcSceneRef(scene);
        ctx.viewport = nullptr;  // TODO: add tc_viewport to ViewportContext if needed
        ctx.camera = vp_ctx.camera;
        ctx.lights = lights;
        ctx.layer_mask = vp_ctx.layer_mask;

        // Execute pass via vtable (works for both C++ and Python passes)
        tc_pass_execute(pass, &ctx);

        tc_profiler_end_section(); // pass_name
    }
    tc_profiler_end_section(); // Execute Passes

    tc_frame_graph_destroy(fg);
}

} // namespace termin
