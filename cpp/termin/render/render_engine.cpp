#include "render_engine.hpp"
#include "tc_log.hpp"

extern "C" {
#include "tc_frame_graph.h"
#include "tc_pass.h"
}

namespace termin {

// ============================================================================
// FBOPool
// ============================================================================

FramebufferHandle* FBOPool::ensure(
    GraphicsBackend* graphics,
    const std::string& key,
    int width,
    int height,
    int samples,
    const std::string& format
) {
    // Find existing entry
    for (auto& entry : entries) {
        if (entry.key == key) {
            // Resize if needed
            if (entry.fbo && (entry.width != width || entry.height != height)) {
                entry.fbo->resize(width, height);
                entry.width = width;
                entry.height = height;
            }
            return entry.fbo.get();
        }
    }

    // Create new entry
    if (!graphics) {
        tc::Log::error("FBOPool::ensure: graphics is null");
        return nullptr;
    }

    auto fbo = graphics->create_framebuffer(width, height, samples, format);
    if (!fbo) {
        tc::Log::error("FBOPool::ensure: failed to create framebuffer '%s'", key.c_str());
        return nullptr;
    }

    FramebufferHandle* ptr = fbo.get();

    FBOPoolEntry entry;
    entry.key = key;
    entry.fbo = std::move(fbo);
    entry.width = width;
    entry.height = height;
    entry.samples = samples;
    entry.format = format;
    entry.external = false;
    entries.push_back(std::move(entry));

    return ptr;
}

FramebufferHandle* FBOPool::get(const std::string& key) {
    for (auto& entry : entries) {
        if (entry.key == key) {
            return entry.fbo.get();
        }
    }
    return nullptr;
}

void FBOPool::set(const std::string& key, FramebufferHandle* fbo) {
    for (auto& entry : entries) {
        if (entry.key == key) {
            // Don't destroy external FBO
            entry.fbo.reset();
            entry.external = true;
            return;
        }
    }

    // Create new external entry
    FBOPoolEntry entry;
    entry.key = key;
    entry.fbo.reset();
    entry.external = true;
    entries.push_back(std::move(entry));
}

void FBOPool::clear() {
    entries.clear();
}

// ============================================================================
// RenderEngine
// ============================================================================

RenderEngine::RenderEngine(GraphicsBackend* graphics)
    : graphics(graphics)
{
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
    tc_resource_spec specs[128] = {};  // Zero-initialize to avoid garbage in unset fields
    size_t spec_count = pipeline->collect_specs(specs, 128);

    // Build spec map for quick lookup
    std::unordered_map<std::string, tc_resource_spec*> spec_map;
    for (size_t i = 0; i < spec_count; i++) {
        spec_map[specs[i].resource] = &specs[i];
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
        tc_resource_spec* spec = nullptr;
        auto it = spec_map.find(canon);
        if (it != spec_map.end()) {
            spec = it->second;
        } else {
            // Try aliases
            const char* aliases[64];
            size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
            for (size_t j = 0; j < alias_count && !spec; j++) {
                auto ait = spec_map.find(aliases[j]);
                if (ait != spec_map.end()) {
                    spec = ait->second;
                }
            }
        }

        // Determine resource type
        const char* resource_type = "fbo";
        if (spec && spec->resource_type[0] != '\0') {
            resource_type = spec->resource_type;
        }

        // Handle shadow_map_array resources
        if (strcmp(resource_type, "shadow_map_array") == 0) {
            auto& shadow_array = shadow_arrays_[canon];
            if (!shadow_array) {
                int resolution = 1024;
                if (spec && spec->fixed_width > 0) {
                    resolution = spec->fixed_width;
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
        if (strcmp(resource_type, "fbo") != 0) {
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
            if (spec->fixed_width > 0) fbo_width = spec->fixed_width;
            if (spec->fixed_height > 0) fbo_height = spec->fixed_height;
            samples = spec->samples > 0 ? spec->samples : 1;
            if (spec->format) format = spec->format;
        }

        // Get or create FBO
        FramebufferHandle* fbo = fbo_pool_.ensure(graphics, canon, fbo_width, fbo_height, samples, format);

        // Set for all aliases
        const char* aliases[64];
        size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
        for (size_t j = 0; j < alias_count; j++) {
            resources[aliases[j]] = fbo;
        }
    }

    // Clear resources according to specs
    for (size_t i = 0; i < spec_count; i++) {
        tc_resource_spec* spec = &specs[i];

        if (strcmp(spec->resource_type, "fbo") != 0 && spec->resource_type[0] != '\0') {
            continue;
        }
        if (!spec->has_clear_color && !spec->has_clear_depth) {
            continue;
        }

        auto it = resources.find(spec->resource);
        if (it == resources.end() || it->second == nullptr) {
            continue;
        }

        FramebufferHandle* fbo = dynamic_cast<FramebufferHandle*>(it->second);
        if (!fbo) continue;

        graphics->bind_framebuffer(fbo);

        int fb_w = spec->fixed_width > 0 ? spec->fixed_width : width;
        int fb_h = spec->fixed_height > 0 ? spec->fixed_height : height;
        graphics->set_viewport(0, 0, fb_w, fb_h);

        if (spec->has_clear_color && spec->has_clear_depth) {
            graphics->clear_color_depth(
                spec->clear_color[0], spec->clear_color[1],
                spec->clear_color[2], spec->clear_color[3]
            );
        } else if (spec->has_clear_color) {
            graphics->clear_color(
                spec->clear_color[0], spec->clear_color[1],
                spec->clear_color[2], spec->clear_color[3]
            );
        } else if (spec->has_clear_depth) {
            graphics->clear_depth(spec->clear_depth);
        }
    }

    // Execute passes in schedule order
    size_t schedule_count = tc_frame_graph_schedule_count(fg);

    for (size_t i = 0; i < schedule_count; i++) {
        tc_pass* pass = tc_frame_graph_schedule_at(fg, i);
        if (!pass || !pass->enabled || pass->passthrough) {
            continue;
        }

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

        // Execute pass via vtable (works for both C++ and Python passes)
        tc_pass_execute(pass, &ctx);
    }

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
    tc_frame_graph* fg = tc_frame_graph_build(pipeline->ptr());
    if (!fg) {
        tc::Log::error("RenderEngine::render_scene_pipeline_offscreen: failed to build frame graph");
        return;
    }

    if (tc_frame_graph_get_error(fg) != TC_FG_OK) {
        tc::Log::error("RenderEngine::render_scene_pipeline_offscreen: frame graph error: %s",
                       tc_frame_graph_get_error_message(fg));
        tc_frame_graph_destroy(fg);
        return;
    }

    // Collect resource specs from pipeline + passes
    tc_resource_spec specs[128] = {};  // Zero-initialize to avoid garbage in unset fields
    size_t spec_count = pipeline->collect_specs(specs, 128);

    std::unordered_map<std::string, tc_resource_spec*> spec_map;
    for (size_t i = 0; i < spec_count; i++) {
        spec_map[specs[i].resource] = &specs[i];
    }

    // Allocate resources based on canonical names from frame graph
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
        tc_resource_spec* spec = nullptr;
        auto it = spec_map.find(canon);
        if (it != spec_map.end()) {
            spec = it->second;
        } else {
            const char* aliases[64];
            size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
            for (size_t j = 0; j < alias_count && !spec; j++) {
                auto ait = spec_map.find(aliases[j]);
                if (ait != spec_map.end()) {
                    spec = ait->second;
                }
            }
        }

        // Determine resource type
        const char* resource_type = "fbo";
        if (spec && spec->resource_type[0] != '\0') {
            resource_type = spec->resource_type;
        }

        // Handle shadow_map_array resources
        if (strcmp(resource_type, "shadow_map_array") == 0) {
            // Get or create ShadowMapArrayResource
            auto& shadow_array = shadow_arrays_[canon];
            if (!shadow_array) {
                int resolution = 1024;
                if (spec && spec->fixed_width > 0) {
                    resolution = spec->fixed_width;
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
        if (strcmp(resource_type, "fbo") != 0) {
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
            if (spec->fixed_width > 0) fbo_width = spec->fixed_width;
            if (spec->fixed_height > 0) fbo_height = spec->fixed_height;
            samples = spec->samples > 0 ? spec->samples : 1;
            if (spec->format) format = spec->format;
        }

        FramebufferHandle* fbo = fbo_pool_.ensure(graphics, canon, fbo_width, fbo_height, samples, format);

        const char* aliases[64];
        size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
        for (size_t j = 0; j < alias_count; j++) {
            resources[aliases[j]] = fbo;
        }
    }

    // Clear resources according to specs
    for (size_t i = 0; i < spec_count; i++) {
        tc_resource_spec* spec = &specs[i];

        if (strcmp(spec->resource_type, "fbo") != 0 && spec->resource_type[0] != '\0') {
            continue;
        }
        if (!spec->has_clear_color && !spec->has_clear_depth) {
            continue;
        }

        auto it = resources.find(spec->resource);
        if (it == resources.end() || it->second == nullptr) {
            continue;
        }

        FramebufferHandle* fbo = dynamic_cast<FramebufferHandle*>(it->second);
        if (!fbo) continue;

        graphics->bind_framebuffer(fbo);

        int fb_w = spec->fixed_width > 0 ? spec->fixed_width : default_width;
        int fb_h = spec->fixed_height > 0 ? spec->fixed_height : default_height;
        graphics->set_viewport(0, 0, fb_w, fb_h);

        if (spec->has_clear_color && spec->has_clear_depth) {
            graphics->clear_color_depth(
                spec->clear_color[0], spec->clear_color[1],
                spec->clear_color[2], spec->clear_color[3]
            );
        } else if (spec->has_clear_color) {
            graphics->clear_color(
                spec->clear_color[0], spec->clear_color[1],
                spec->clear_color[2], spec->clear_color[3]
            );
        } else if (spec->has_clear_depth) {
            graphics->clear_depth(spec->clear_depth);
        }
    }

    // Execute passes in schedule order
    size_t schedule_count = tc_frame_graph_schedule_count(fg);

    for (size_t i = 0; i < schedule_count; i++) {
        tc_pass* pass = tc_frame_graph_schedule_at(fg, i);
        if (!pass || !pass->enabled || pass->passthrough) {
            continue;
        }

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
    }

    tc_frame_graph_destroy(fg);
}

} // namespace termin
