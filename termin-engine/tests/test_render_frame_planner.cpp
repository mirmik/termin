#include "render_frame_planner.hpp"

#include <cstddef>
#include <cstdio>
#include <cstring>

extern "C" {
#include "core/tc_scene.h"
#include "core/tc_scene_render_mount.h"
#include "render/tc_display.h"
#include "render/tc_pipeline_template_registry.h"
#include "render/tc_render_surface.h"
#include "render/tc_render_target.h"
#include "render/tc_viewport.h"
#include "termin_scene/internal/tc_scene_extension_registry.h"
}

namespace {

using termin::RenderTopology;
using termin::rendering_manager_detail::OffscreenRenderDiagnostic;
using termin::rendering_manager_detail::OffscreenRenderDiagnosticKind;
using termin::rendering_manager_detail::OffscreenRenderDemand;
using termin::rendering_manager_detail::OffscreenRenderJob;
using termin::rendering_manager_detail::OffscreenRenderJobKind;
using termin::rendering_manager_detail::OffscreenRenderPlanner;

struct TestPipeline {
    tc_pipeline_template_handle pipeline_template = tc_pipeline_template_handle_invalid();
    tc_pipeline_handle pipeline = TC_PIPELINE_HANDLE_INVALID;
};

struct Param {
    const char* slot;
    const char* value;
};

struct Recorder {
    OffscreenRenderJob jobs[16]{};
    size_t job_count = 0;
    OffscreenRenderDiagnostic diagnostics[16]{};
    size_t diagnostic_count = 0;
};

struct FixedSurface {
    tc_render_surface surface{};
    int width = 0;
    int height = 0;
};

void surface_get_size(tc_render_surface* surface, int* width, int* height) {
    FixedSurface* fixed = static_cast<FixedSurface*>(surface->body);
    if (width) *width = fixed->width;
    if (height) *height = fixed->height;
}

uint32_t surface_get_texture(tc_render_surface*) { return 1; }
uintptr_t surface_get_domain(tc_render_surface*) { return 1; }
void surface_destroy(tc_render_surface*) {}
bool surface_resize(tc_render_surface* surface, int width, int height) {
    FixedSurface* fixed = static_cast<FixedSurface*>(surface->body);
    fixed->width = width;
    fixed->height = height;
    tc_render_surface_notify_resize(surface, width, height);
    return true;
}
void surface_delete(tc_render_surface* surface) {
    delete static_cast<FixedSurface*>(surface->body);
}

const tc_render_surface_vtable FIXED_SURFACE_VTABLE = {
    .get_size = surface_get_size,
    .resize = surface_resize,
    .get_color_texture_id = surface_get_texture,
    .get_graphics_domain_key = surface_get_domain,
    .destroy = surface_destroy,
};

TestPipeline make_pipeline(
    const char* uuid,
    const char* name,
    const char* const* external_slots,
    size_t external_slot_count,
    const char* const* viewport_targets = nullptr,
    size_t viewport_target_count = 0
) {
    TestPipeline result;
    result.pipeline_template = tc_pipeline_template_create(uuid, name);
    tc_pipeline_template* pipeline_template = tc_pipeline_template_get(result.pipeline_template);
    tc_pipeline_template_resource_desc resources[8]{};
    tc_pipeline_template_target_desc targets[8]{};
    if (external_slot_count > 8 || viewport_target_count > 8) return result;
    for (size_t i = 0; i < external_slot_count; ++i) {
        resources[i] = {
            external_slots[i], "external", nullptr, nullptr, 0, 0, 1.0f, 1, 0};
    }
    for (size_t i = 0; i < viewport_target_count; ++i) {
        targets[i] = {viewport_targets[i], nullptr, 0, 0};
    }
    const tc_pipeline_template_payload_desc payload{
        TC_PIPELINE_TEMPLATE_DESCRIPTOR_VERSION,
        name,
        nullptr,
        0,
        resources,
        static_cast<uint32_t>(external_slot_count),
        nullptr,
        0,
        targets,
        static_cast<uint32_t>(viewport_target_count),
    };
    if (!pipeline_template || !tc_pipeline_template_set_payload(pipeline_template, &payload)) {
        return result;
    }
    result.pipeline = tc_pipeline_create_from_template(result.pipeline_template);
    return result;
}

void destroy_pipeline(TestPipeline& pipeline) {
    if (tc_pipeline_handle_valid(pipeline.pipeline)) tc_pipeline_destroy(pipeline.pipeline);
    if (tc_pipeline_template_is_valid(pipeline.pipeline_template)) {
        tc_pipeline_template_remove(pipeline.pipeline_template);
    }
}

void set_params(tc_render_target_handle target, const Param* params, size_t count) {
    tc_value dict = tc_value_dict_new();
    for (size_t i = 0; i < count; ++i) {
        tc_value_dict_set(&dict, params[i].slot, tc_value_string(params[i].value));
    }
    tc_render_target_set_pipeline_params(target, &dict);
    tc_value_free(&dict);
}

void record_job(void* user_data, const OffscreenRenderJob* job) {
    Recorder* recorder = static_cast<Recorder*>(user_data);
    if (recorder->job_count < 16) recorder->jobs[recorder->job_count++] = *job;
}

void record_diagnostic(void* user_data, const OffscreenRenderDiagnostic* diagnostic) {
    Recorder* recorder = static_cast<Recorder*>(user_data);
    if (recorder->diagnostic_count < 16) {
        recorder->diagnostics[recorder->diagnostic_count++] = *diagnostic;
    }
}

const OffscreenRenderJob* find_target_job(
    const Recorder& recorder,
    tc_render_target_handle target
) {
    for (size_t i = 0; i < recorder.job_count; ++i) {
        if (recorder.jobs[i].kind == OffscreenRenderJobKind::RenderTarget
                && tc_render_target_handle_eq(recorder.jobs[i].render_target, target)) {
            return &recorder.jobs[i];
        }
    }
    return nullptr;
}

size_t target_job_index(const Recorder& recorder, tc_render_target_handle target) {
    for (size_t i = 0; i < recorder.job_count; ++i) {
        if (recorder.jobs[i].kind == OffscreenRenderJobKind::RenderTarget
                && tc_render_target_handle_eq(recorder.jobs[i].render_target, target)) {
            return i;
        }
    }
    return recorder.job_count;
}

bool contains_diagnostic(
    const Recorder& recorder,
    OffscreenRenderDiagnosticKind kind
) {
    for (size_t i = 0; i < recorder.diagnostic_count; ++i) {
        if (recorder.diagnostics[i].kind == kind) return true;
    }
    return false;
}

bool execute_plan(
    OffscreenRenderPlanner& planner,
    const RenderTopology& topology,
    Recorder& recorder,
    tc_display_handle only_display = TC_DISPLAY_HANDLE_INVALID,
    const OffscreenRenderDemand* demands = nullptr,
    size_t demand_count = 0
) {
    recorder = Recorder{};
    return planner.execute(
        topology,
        only_display,
        record_job,
        &recorder,
        record_diagnostic,
        &recorder,
        demands,
        demand_count);
}

} // namespace

int main() {
    tc_display_pool_init();
    tc_pipeline_template_init();
    tc_scene_ext_registry_init();
    tc_scene_render_mount_extension_init();

    tc_scene_handle scene = tc_scene_new_named("render-frame-planner-test");
    if (!tc_scene_handle_valid(scene)) return 1;
    const char* consumer_slots[] = {"fov", "file_tex"};
    const char* cycle_slots[] = {"consumer"};
    TestPipeline producer_pipeline = make_pipeline(
        "render-frame-planner-producer", "Producer", nullptr, 0);
    TestPipeline consumer_pipeline = make_pipeline(
        "render-frame-planner-consumer", "Consumer", consumer_slots, 2);
    TestPipeline cycle_pipeline = make_pipeline(
        "render-frame-planner-cycle", "CycleProducer", cycle_slots, 1);
    if (!tc_pipeline_handle_valid(producer_pipeline.pipeline)
            || !tc_pipeline_handle_valid(consumer_pipeline.pipeline)
            || !tc_pipeline_handle_valid(cycle_pipeline.pipeline)) return 1;

    RenderTopology topology;
    tc_render_target_handle producer = tc_render_target_new("FovTarget");
    tc_render_target_handle unused = tc_render_target_new("UnusedHiddenTarget");
    tc_render_target_handle consumer = tc_render_target_new("chronosquad");
    tc_render_target_handle unattached = tc_render_target_new("UnattachedTarget");
    const tc_render_target_handle render_targets[] = {
        producer, unused, consumer, unattached};
    for (tc_render_target_handle target : render_targets) {
        tc_render_target_set_scene(target, scene);
        if (!topology.register_render_target(target)) return 1;
    }
    tc_render_target_set_pipeline(producer, producer_pipeline.pipeline);
    tc_render_target_set_pipeline(unused, producer_pipeline.pipeline);
    tc_render_target_set_pipeline(consumer, consumer_pipeline.pipeline);
    tc_render_target_set_pipeline(unattached, producer_pipeline.pipeline);
    const Param consumer_params[] = {
        {"fov", "FovTarget"},
        {"file_tex", "file:test-texture"},
        {"unnamed", "UnusedHiddenTarget"},
    };
    set_params(consumer, consumer_params, 3);

    auto* active_surface = new FixedSurface;
    active_surface->width = 800;
    active_surface->height = 600;
    tc_render_surface_init(
        &active_surface->surface, &FIXED_SURFACE_VTABLE, surface_delete);
    active_surface->surface.body = active_surface;
    auto* hidden_surface = new FixedSurface;
    hidden_surface->width = 320;
    hidden_surface->height = 200;
    tc_render_surface_init(
        &hidden_surface->surface, &FIXED_SURFACE_VTABLE, surface_delete);
    hidden_surface->surface.body = hidden_surface;
    tc_display_handle active_display = tc_display_new("Display 0", &active_surface->surface);
    tc_display_handle hidden_display = tc_display_new("Display 1", &hidden_surface->surface);
    tc_viewport_handle consumer_viewport = tc_viewport_new("chronosquad", scene);
    tc_viewport_handle producer_viewport = tc_viewport_new("test_vp", scene);
    tc_viewport_handle unused_viewport = tc_viewport_new("unused_vp", scene);
    tc_viewport_set_render_target(consumer_viewport, consumer);
    tc_viewport_set_render_target(producer_viewport, producer);
    tc_viewport_set_render_target(unused_viewport, unused);
    tc_display_add_viewport(active_display, consumer_viewport);
    tc_display_add_viewport(hidden_display, producer_viewport);
    tc_display_add_viewport(hidden_display, unused_viewport);
    topology.register_viewport(scene, consumer_viewport, active_display);
    topology.register_viewport(scene, producer_viewport, hidden_display);
    topology.register_viewport(scene, unused_viewport, hidden_display);
    tc_display_set_enabled(hidden_display, false);

    tc_render_target_set_dynamic_resolution(consumer, true);
    tc_render_target_set_width(consumer, 64);
    tc_render_target_set_height(consumer, 64);
    tc_render_target_set_width(producer, 2048);
    tc_render_target_set_height(producer, 8192);
    termin::rendering_manager_detail::update_viewport_rects(topology);
    termin::rendering_manager_detail::sync_viewport_render_target_resolutions(topology);
    if (tc_render_target_get_width(consumer) != 800
            || tc_render_target_get_height(consumer) != 600
            || tc_render_target_get_width(producer) != 2048
            || tc_render_target_get_height(producer) != 8192) {
        std::fprintf(stderr, "viewport sizing phase did not commit the expected RT sizes\n");
        return 1;
    }

    OffscreenRenderPlanner planner;
    Recorder recorder;
    if (!execute_plan(planner, topology, recorder)) return 1;
    const OffscreenRenderJob* producer_job = find_target_job(recorder, producer);
    const OffscreenRenderJob* consumer_job = find_target_job(recorder, consumer);
    if (recorder.job_count != 2
            || target_job_index(recorder, producer) >= target_job_index(recorder, consumer)
            || !producer_job || tc_viewport_handle_valid(producer_job->viewport)
            || !consumer_job
            || !tc_viewport_handle_eq(consumer_job->viewport, consumer_viewport)
            || find_target_job(recorder, unused)
            || find_target_job(recorder, unattached)) {
        std::fprintf(stderr, "active consumer did not schedule its hidden producer first\n");
        return 1;
    }

    if (!execute_plan(planner, topology, recorder, active_display)
            || recorder.job_count != 2
            || target_job_index(recorder, producer) >= target_job_index(recorder, consumer)) {
        std::fprintf(stderr, "selected-display plan lost dependency closure\n");
        return 1;
    }

    const OffscreenRenderDemand debugger_demand{unused_viewport, unused};
    if (!execute_plan(
            planner,
            topology,
            recorder,
            active_display,
            &debugger_demand,
            1)
            || recorder.job_count != 3
            || !find_target_job(recorder, unused)
            || !tc_viewport_handle_eq(
                find_target_job(recorder, unused)->viewport, unused_viewport)
            || target_job_index(recorder, producer) >= target_job_index(recorder, consumer)) {
        std::fprintf(
            stderr,
            "debugger demand did not activate hidden target with dependency closure\n");
        return 1;
    }

    // Editor/host targets are externally owned and therefore are not present
    // in managed_render_targets. Their registered viewport attachment must
    // still create a schedulable root job.
    RenderTopology editor_topology;
    tc_render_target_handle editor_target = tc_render_target_new("(Editor)");
    tc_render_target_set_scene(editor_target, scene);
    tc_render_target_set_pipeline(editor_target, producer_pipeline.pipeline);
    tc_render_target_set_dynamic_resolution(editor_target, true);
    tc_display_handle editor_display = tc_display_new("Editor", nullptr);
    tc_viewport_handle editor_viewport = tc_viewport_new("(Editor)", scene);
    tc_viewport_set_render_target(editor_viewport, editor_target);
    tc_display_add_viewport(editor_display, editor_viewport);
    if (!editor_topology.register_viewport(scene, editor_viewport, editor_display, false)
            || !execute_plan(planner, editor_topology, recorder, editor_display)
            || recorder.job_count != 1
            || !find_target_job(recorder, editor_target)
            || !tc_viewport_handle_eq(recorder.jobs[0].viewport, editor_viewport)) {
        std::fprintf(stderr, "externally owned editor target was not scheduled\n");
        return 1;
    }
    editor_topology.unregister_viewport(editor_viewport);
    tc_display_remove_viewport(editor_display, editor_viewport);
    tc_viewport_free(editor_viewport);
    tc_display_free(editor_display);
    tc_render_target_free(editor_target);

    tc_render_target_set_pipeline(producer, cycle_pipeline.pipeline);
    const Param cycle_params[] = {{"consumer", "chronosquad"}};
    set_params(producer, cycle_params, 1);
    if (execute_plan(planner, topology, recorder)
            || !contains_diagnostic(recorder, OffscreenRenderDiagnosticKind::DependencyCycle)
            || find_target_job(recorder, producer)
            || find_target_job(recorder, consumer)) {
        std::fprintf(stderr, "dependency cycle was not diagnosed and suppressed\n");
        return 1;
    }

    tc_scene_handle atomic_scene = tc_scene_new_named("atomic-pipeline-test");
    const char* atomic_targets[] = {"atomic_active", "atomic_hidden"};
    TestPipeline atomic_pipeline = make_pipeline(
        "render-frame-planner-atomic", "AtomicPipeline", nullptr, 0, atomic_targets, 2);
    RenderTopology atomic_topology;
    tc_render_target_handle atomic_active_target = tc_render_target_new("AtomicActiveTarget");
    tc_render_target_handle atomic_hidden_target = tc_render_target_new("AtomicHiddenTarget");
    tc_render_target_set_scene(atomic_active_target, atomic_scene);
    tc_render_target_set_scene(atomic_hidden_target, atomic_scene);
    atomic_topology.register_render_target(atomic_active_target);
    atomic_topology.register_render_target(atomic_hidden_target);
    tc_display_handle atomic_active_display = tc_display_new("Atomic Display 0", nullptr);
    tc_display_handle atomic_hidden_display = tc_display_new("Atomic Display 1", nullptr);
    tc_viewport_handle atomic_active_viewport = tc_viewport_new("atomic_active", atomic_scene);
    tc_viewport_handle atomic_hidden_viewport = tc_viewport_new("atomic_hidden", atomic_scene);
    tc_viewport_set_render_target(atomic_active_viewport, atomic_active_target);
    tc_viewport_set_render_target(atomic_hidden_viewport, atomic_hidden_target);
    tc_display_add_viewport(atomic_active_display, atomic_active_viewport);
    tc_display_add_viewport(atomic_hidden_display, atomic_hidden_viewport);
    atomic_topology.register_viewport(atomic_scene, atomic_active_viewport, atomic_active_display);
    atomic_topology.register_viewport(atomic_scene, atomic_hidden_viewport, atomic_hidden_display);
    tc_display_set_enabled(atomic_hidden_display, false);
    if (!tc_scene_add_pipeline_template(atomic_scene, atomic_pipeline.pipeline_template)
            || !atomic_topology.attach_scene(atomic_scene)
            || !execute_plan(planner, atomic_topology, recorder)
            || recorder.job_count != 1
            || recorder.jobs[0].kind != OffscreenRenderJobKind::ScenePipeline
            || atomic_topology.pipeline_target_count(
                atomic_scene, recorder.jobs[0].pipeline) != 2) {
        std::fprintf(stderr, "scene pipeline was not planned as one atomic job\n");
        return 1;
    }

    atomic_topology.detach_scene(atomic_scene);
    tc_scene_clear_pipeline_templates(atomic_scene);
    atomic_topology.unregister_viewport(atomic_active_viewport);
    atomic_topology.unregister_viewport(atomic_hidden_viewport);
    tc_display_remove_viewport(atomic_active_display, atomic_active_viewport);
    tc_display_remove_viewport(atomic_hidden_display, atomic_hidden_viewport);
    tc_viewport_free(atomic_active_viewport);
    tc_viewport_free(atomic_hidden_viewport);
    tc_display_free(atomic_active_display);
    tc_display_free(atomic_hidden_display);
    atomic_topology.unregister_render_target(atomic_active_target);
    atomic_topology.unregister_render_target(atomic_hidden_target);
    tc_render_target_free(atomic_active_target);
    tc_render_target_free(atomic_hidden_target);
    destroy_pipeline(atomic_pipeline);
    tc_scene_free(atomic_scene);

    topology.unregister_viewport(consumer_viewport);
    topology.unregister_viewport(producer_viewport);
    topology.unregister_viewport(unused_viewport);
    tc_display_remove_viewport(active_display, consumer_viewport);
    tc_display_remove_viewport(hidden_display, producer_viewport);
    tc_display_remove_viewport(hidden_display, unused_viewport);
    tc_viewport_free(consumer_viewport);
    tc_viewport_free(producer_viewport);
    tc_viewport_free(unused_viewport);
    tc_display_free(active_display);
    tc_display_free(hidden_display);
    for (tc_render_target_handle target : render_targets) {
        topology.unregister_render_target(target);
        tc_render_target_free(target);
    }
    destroy_pipeline(producer_pipeline);
    destroy_pipeline(consumer_pipeline);
    destroy_pipeline(cycle_pipeline);
    tc_scene_free(scene);
    tc_scene_ext_registry_shutdown();
    tc_pipeline_template_shutdown();
    tc_display_pool_shutdown();
    return 0;
}
