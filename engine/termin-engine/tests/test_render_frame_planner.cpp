#include "render_frame_planner.hpp"
#include "termin/render/render_scene_item_collector.hpp"

#include <cstddef>
#include <cstdio>
#include <cstring>

extern "C" {
#include "core/tc_drawable_capability.h"
#include "core/tc_drawable_protocol.h"
#include "core/tc_entity_pool.h"
#include "core/tc_render_item.h"
#include "core/tc_scene.h"
#include "core/tc_scene_render_mount.h"
#include "render/tc_display.h"
#include "render/tc_pipeline_template_registry.h"
#include "render/tc_render_surface.h"
#include "render/tc_render_target.h"
#include "render/tc_viewport.h"
#include "termin_scene/internal/tc_scene_extension_registry.h"
#include "tgfx/resources/tc_material_registry.h"
#include "tcbase/tc_log.h"
}

namespace {

    using termin::RenderTopology;
    using termin::rendering_manager_detail::OffscreenRenderDemand;
    using termin::rendering_manager_detail::OffscreenRenderDiagnostic;
    using termin::rendering_manager_detail::OffscreenRenderDiagnosticKind;
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

    struct DependencyProducer {
        tc_material_handle materials[8]{};
        size_t material_count = 0;
        // A producer with only a borrowed phase still reports its owner's
        // handle in the lightweight enumeration contract.
        const tc_material_phase* owner_phase = nullptr;
        uint64_t category = 1;
        size_t material_calls = 0;
        size_t heavy_calls = 0;
        tc_render_item_collect_context last_context{};
    };

    size_t g_error_log_count = 0;

    void record_log(tc_log_level level, const char*) {
        if (level == TC_LOG_ERROR)
            ++g_error_log_count;
    }

    bool discard_material(tc_material_handle, void*) {
        return true;
    }

    tc_material_handle make_dependency_material(const char* uuid, const char* target) {
        tc_material_handle handle = tc_material_create(uuid, uuid);
        tc_material* material = tc_material_get(handle);
        if (!material)
            return tc_material_handle_invalid();
        material->phase_count = 1;
        material->phases[0].owner_material = handle;
        material->phases[0].owner_phase_index = 0;
        if (!tc_material_phase_declare_texture_slot(&material->phases[0], "u_input") ||
            !tc_material_set_texture_source(material, "u_input", "render_target", target, "color")) {
            tc_material_destroy(handle);
            return tc_material_handle_invalid();
        }
        return handle;
    }

    tc_phase_mask dependency_phase_mask(tc_component*) {
        return TC_PHASE_OPAQUE;
    }

    bool collect_dependency_item(tc_component* component,
                                 const tc_render_item_collect_context*,
                                 tc_render_item_sink*) {
        auto* producer = static_cast<DependencyProducer*>(tc_component_get_drawable_userdata(component));
        ++producer->heavy_calls;
        std::fprintf(stderr, "planner called the heavy RenderItem producer\n");
        return false;
    }

    bool collect_dependency_materials(tc_component* component,
                                      const tc_render_item_collect_context* context,
                                      tc_material_sink* sink) {
        auto* producer = static_cast<DependencyProducer*>(tc_component_get_drawable_userdata(component));
        ++producer->material_calls;
        producer->last_context = *context;
        if ((producer->category & context->render_category_mask) == 0)
            return true;
        if (producer->owner_phase && !sink->emit(producer->owner_phase->owner_material, sink->user_data))
            return false;
        for (size_t i = 0; i < producer->material_count; ++i) {
            if (!sink->emit(producer->materials[i], sink->user_data))
                return false;
        }
        return true;
    }

    const tc_drawable_vtable DEPENDENCY_DRAWABLE_VTABLE = {
        &dependency_phase_mask,
        &collect_dependency_item,
        &collect_dependency_materials,
    };

    const tc_drawable_vtable MISSING_ENUMERATION_VTABLE = {
        &dependency_phase_mask,
        &collect_dependency_item,
        nullptr,
    };

    void surface_get_size(tc_render_surface* surface, int* width, int* height) {
        FixedSurface* fixed = static_cast<FixedSurface*>(surface->body);
        if (width)
            *width = fixed->width;
        if (height)
            *height = fixed->height;
    }

    uint32_t surface_get_texture(tc_render_surface*) {
        return 1;
    }
    uintptr_t surface_get_domain(tc_render_surface*) {
        return 1;
    }
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

    TestPipeline make_pipeline(const char* uuid,
                               const char* name,
                               const char* const* external_slots,
                               size_t external_slot_count,
                               const char* const* viewport_targets = nullptr,
                               size_t viewport_target_count = 0) {
        TestPipeline result;
        result.pipeline_template = tc_pipeline_template_create(uuid, name);
        tc_pipeline_template* pipeline_template = tc_pipeline_template_get(result.pipeline_template);
        tc_pipeline_template_resource_desc resources[8]{};
        tc_pipeline_template_target_desc targets[8]{};
        if (external_slot_count > 8 || viewport_target_count > 8)
            return result;
        for (size_t i = 0; i < external_slot_count; ++i) {
            resources[i] = {external_slots[i], "external", nullptr, nullptr, 0, 0, 1.0f, 1, 1, 0};
        }
        for (size_t i = 0; i < viewport_target_count; ++i) {
            targets[i] = {viewport_targets[i], nullptr, TC_COLOR_CONTENT_DISPLAY_LINEAR, 0, 0};
        }
        const tc_pipeline_template_payload_desc payload{
            TC_PIPELINE_TEMPLATE_DESCRIPTOR_VERSION,
            TC_PIPELINE_EXECUTION_SINGLE_VIEW,
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
        if (tc_pipeline_handle_valid(pipeline.pipeline))
            tc_pipeline_destroy(pipeline.pipeline);
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
        if (recorder->job_count < 16)
            recorder->jobs[recorder->job_count++] = *job;
    }

    void record_diagnostic(void* user_data, const OffscreenRenderDiagnostic* diagnostic) {
        Recorder* recorder = static_cast<Recorder*>(user_data);
        if (recorder->diagnostic_count < 16) {
            recorder->diagnostics[recorder->diagnostic_count++] = *diagnostic;
        }
    }

    const OffscreenRenderJob* find_target_job(const Recorder& recorder, tc_render_target_handle target) {
        for (size_t i = 0; i < recorder.job_count; ++i) {
            if (recorder.jobs[i].kind == OffscreenRenderJobKind::RenderTarget &&
                tc_render_target_handle_eq(recorder.jobs[i].render_target, target)) {
                return &recorder.jobs[i];
            }
        }
        return nullptr;
    }

    size_t target_job_index(const Recorder& recorder, tc_render_target_handle target) {
        for (size_t i = 0; i < recorder.job_count; ++i) {
            if (recorder.jobs[i].kind == OffscreenRenderJobKind::RenderTarget &&
                tc_render_target_handle_eq(recorder.jobs[i].render_target, target)) {
                return i;
            }
        }
        return recorder.job_count;
    }

    bool contains_diagnostic(const Recorder& recorder, OffscreenRenderDiagnosticKind kind) {
        for (size_t i = 0; i < recorder.diagnostic_count; ++i) {
            if (recorder.diagnostics[i].kind == kind)
                return true;
        }
        return false;
    }

    bool execute_plan(OffscreenRenderPlanner& planner,
                      const RenderTopology& topology,
                      Recorder& recorder,
                      tc_display_handle only_display = TC_DISPLAY_HANDLE_INVALID,
                      const OffscreenRenderDemand* demands = nullptr,
                      size_t demand_count = 0) {
        recorder.job_count = 0;
        recorder.diagnostic_count = 0;
        return planner.execute(
            topology, only_display, record_job, &recorder, record_diagnostic, &recorder, demands, demand_count);
    }

    struct SelectionContext {
        uint64_t categories = UINT64_MAX;
        int scene_marker = 0;
        int camera_marker = 0;
    };

    bool collect_selected_materials(void* user_data,
                                    const OffscreenRenderJob*,
                                    tc_render_target_handle output,
                                    tc_material_sink* sink) {
        auto* selection = static_cast<SelectionContext*>(user_data);
        termin::RenderSceneItemCollectRequest request;
        request.scene = tc_render_target_get_scene(output);
        request.layer_mask = tc_render_target_get_layer_mask(output);
        request.render_category_mask = selection->categories;
        request.scene_context = &selection->scene_marker;
        request.camera = &selection->camera_marker;
        request.user_context = selection;
        return termin::collect_scene_materials(request, *sink);
    }

    bool execute_selected_plan(OffscreenRenderPlanner& planner,
                               const RenderTopology& topology,
                               Recorder& recorder,
                               SelectionContext& selection) {
        recorder.job_count = 0;
        recorder.diagnostic_count = 0;
        return planner.execute(topology,
                               TC_DISPLAY_HANDLE_INVALID,
                               record_job,
                               &recorder,
                               record_diagnostic,
                               &recorder,
                               nullptr,
                               0,
                               collect_selected_materials,
                               &selection);
    }

} // namespace

int main() {
    tc_display_pool_init();
    tc_pipeline_template_init();
    tc_scene_ext_registry_init();
    tc_scene_render_mount_extension_init();
    tc_material_init();
    tc_log_set_callback(record_log);

    tc_scene_handle scene = tc_scene_new_named("render-frame-planner-test");
    if (!tc_scene_handle_valid(scene))
        return 1;
    tc_material_handle g_dependency_material = make_dependency_material("planner-material-source", "FovTarget");
    tc_material* dependency_material = tc_material_get(g_dependency_material);
    if (!dependency_material)
        return 1;
    DependencyProducer dependency_producer;
    dependency_producer.materials[0] = g_dependency_material;
    dependency_producer.material_count = 1;
    tc_entity_pool* scene_pool = tc_scene_entity_pool(scene);
    tc_entity_id dependency_entity = tc_entity_pool_alloc(scene_pool, "material-source-consumer");
    tc_component dependency_component{};
    tc_component_init(&dependency_component, nullptr);
    tc_entity_pool_add_component(scene_pool, dependency_entity, &dependency_component);
    if (!tc_drawable_capability_attach(
            &dependency_component, &DEPENDENCY_DRAWABLE_VTABLE, &dependency_producer)) {
        return 1;
    }
    const char* consumer_slots[] = {"fov", "file_tex"};
    const char* cycle_slots[] = {"consumer"};
    TestPipeline producer_pipeline = make_pipeline("render-frame-planner-producer", "Producer", nullptr, 0);
    TestPipeline consumer_pipeline = make_pipeline("render-frame-planner-consumer", "Consumer", consumer_slots, 2);
    TestPipeline cycle_pipeline = make_pipeline("render-frame-planner-cycle", "CycleProducer", cycle_slots, 1);
    if (!tc_pipeline_handle_valid(producer_pipeline.pipeline) ||
        !tc_pipeline_handle_valid(consumer_pipeline.pipeline) || !tc_pipeline_handle_valid(cycle_pipeline.pipeline))
        return 1;

    RenderTopology topology;
    tc_render_target_handle producer = tc_render_target_new("FovTarget");
    tc_render_target_handle unused = tc_render_target_new("UnusedHiddenTarget");
    tc_render_target_handle consumer = tc_render_target_new("chronosquad");
    tc_render_target_handle unattached = tc_render_target_new("UnattachedTarget");
    // The producer renders a different layer than the consumer geometry, just
    // like the panel UI target in the Quest showcase. This prevents a genuine
    // feedback loop through the material that displays the producer result.
    tc_render_target_set_layer_mask(producer, 2u);
    tc_render_target_set_layer_mask(consumer, 1u);
    tc_render_target_set_layer_mask(unused, 4u);
    tc_render_target_set_layer_mask(unattached, 8u);
    const tc_render_target_handle render_targets[] = {producer, unused, consumer, unattached};
    for (tc_render_target_handle target : render_targets) {
        tc_render_target_set_scene(target, scene);
        if (!topology.register_render_target(target))
            return 1;
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
    tc_render_surface_init(&active_surface->surface, &FIXED_SURFACE_VTABLE, surface_delete);
    active_surface->surface.body = active_surface;
    auto* hidden_surface = new FixedSurface;
    hidden_surface->width = 320;
    hidden_surface->height = 200;
    tc_render_surface_init(&hidden_surface->surface, &FIXED_SURFACE_VTABLE, surface_delete);
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
    if (tc_render_target_get_width(consumer) != 800 || tc_render_target_get_height(consumer) != 600 ||
        tc_render_target_get_width(producer) != 2048 || tc_render_target_get_height(producer) != 8192) {
        std::fprintf(stderr, "viewport sizing phase did not commit the expected RT sizes\n");
        return 1;
    }

    OffscreenRenderPlanner planner;
    Recorder recorder;
    if (!execute_plan(planner, topology, recorder))
        return 1;
    const OffscreenRenderJob* producer_job = find_target_job(recorder, producer);
    const OffscreenRenderJob* consumer_job = find_target_job(recorder, consumer);
    if (recorder.job_count != 2 || target_job_index(recorder, producer) >= target_job_index(recorder, consumer) ||
        !producer_job || tc_viewport_handle_valid(producer_job->viewport) || !consumer_job ||
        !tc_viewport_handle_eq(consumer_job->viewport, consumer_viewport) || find_target_job(recorder, unused) ||
        find_target_job(recorder, unattached)) {
        std::fprintf(stderr, "active consumer did not schedule its hidden producer first\n");
        return 1;
    }

    if (!execute_plan(planner, topology, recorder, active_display) || recorder.job_count != 2 ||
        target_job_index(recorder, producer) >= target_job_index(recorder, consumer)) {
        std::fprintf(stderr, "selected-display plan lost dependency closure\n");
        return 1;
    }

    // Remove the graph slot: the symbolic source on the material is now the
    // only edge from the consumer to FovTarget.
    const Param material_only_params[] = {{"file_tex", "file:test-texture"}};
    set_params(consumer, material_only_params, 1);
    if (!execute_plan(planner, topology, recorder) || recorder.job_count != 2 ||
        target_job_index(recorder, producer) >= target_job_index(recorder, consumer)) {
        std::fprintf(stderr, "material render-target source did not schedule its producer first\n");
        return 1;
    }
    if (!dependency_producer.material_calls || dependency_producer.heavy_calls != 0) {
        std::fprintf(stderr, "material dependency planning did not use only lightweight enumeration\n");
        return 1;
    }

    // Texture-source edits and material replacement must take effect on the
    // next plan, rather than retaining the dependency closure of a prior frame.
    if (!tc_material_set_texture_source(dependency_material, "u_input", "render_target", "UnusedHiddenTarget", "color") ||
        !execute_plan(planner, topology, recorder) || recorder.job_count != 2 ||
        find_target_job(recorder, producer) || !find_target_job(recorder, unused) ||
        target_job_index(recorder, unused) >= target_job_index(recorder, consumer)) {
        std::fprintf(stderr, "runtime texture-source edit left a stale material dependency\n");
        return 1;
    }
    tc_material_handle alternate_material = make_dependency_material("planner-material-alternate", "UnattachedTarget");
    if (!tc_material_get(alternate_material))
        return 1;
    dependency_producer.materials[0] = alternate_material;
    if (!execute_plan(planner, topology, recorder) || recorder.job_count != 2 ||
        find_target_job(recorder, producer) || find_target_job(recorder, unused) ||
        target_job_index(recorder, unattached) >= target_job_index(recorder, consumer)) {
        std::fprintf(stderr, "runtime material replacement left a stale material dependency\n");
        return 1;
    }
    if (!tc_material_set_texture_source(dependency_material, "u_input", "render_target", "FovTarget", "color"))
        return 1;
    dependency_producer.materials[0] = g_dependency_material;

    dependency_producer.material_count = 0;
    dependency_producer.owner_phase = &dependency_material->phases[0];
    if (!execute_plan(planner, topology, recorder) || recorder.job_count != 2 ||
        target_job_index(recorder, producer) >= target_job_index(recorder, consumer)) {
        std::fprintf(stderr, "phase-only producer failed to enumerate its owner material\n");
        return 1;
    }
    dependency_producer.owner_phase = nullptr;
    dependency_producer.material_count = 1;

    // Scene filters exclude the producer before material enumeration, so an
    // invisible or disabled drawable cannot activate a hidden target.
    auto assert_filtered = [&]() {
        const size_t previous_calls = dependency_producer.material_calls;
        return execute_plan(planner, topology, recorder) && recorder.job_count == 1 &&
               find_target_job(recorder, consumer) && !find_target_job(recorder, producer) &&
               dependency_producer.material_calls == previous_calls;
    };
    tc_component_set_enabled(&dependency_component, false);
    if (!assert_filtered()) {
        std::fprintf(stderr, "disabled component contributed a material dependency\n");
        return 1;
    }
    tc_component_set_enabled(&dependency_component, true);
    tc_entity_pool_set_visible(scene_pool, dependency_entity, false);
    if (!assert_filtered()) {
        std::fprintf(stderr, "invisible entity contributed a material dependency\n");
        return 1;
    }
    tc_entity_pool_set_visible(scene_pool, dependency_entity, true);
    tc_entity_pool_set_enabled(scene_pool, dependency_entity, false);
    if (!assert_filtered()) {
        std::fprintf(stderr, "disabled entity contributed a material dependency\n");
        return 1;
    }
    tc_entity_pool_set_enabled(scene_pool, dependency_entity, true);
    tc_entity_pool_set_layer(scene_pool, dependency_entity, 4u);
    if (!assert_filtered()) {
        std::fprintf(stderr, "entity outside the target layer mask contributed a material dependency\n");
        return 1;
    }
    tc_entity_pool_set_layer(scene_pool, dependency_entity, 0u);
    tc_render_target_set_layer_mask(consumer, 0u);
    if (!assert_filtered()) {
        std::fprintf(stderr, "empty target layer mask contributed a material dependency\n");
        return 1;
    }
    tc_render_target_set_layer_mask(consumer, 1u);

    SelectionContext selection;
    selection.categories = 2u;
    if (!execute_selected_plan(planner, topology, recorder, selection) || recorder.job_count != 1 ||
        !find_target_job(recorder, consumer) || find_target_job(recorder, producer)) {
        std::fprintf(stderr, "excluded render category contributed a material dependency\n");
        return 1;
    }
    selection.categories = 1u;
    if (!execute_selected_plan(planner, topology, recorder, selection) || recorder.job_count != 2 ||
        target_job_index(recorder, producer) >= target_job_index(recorder, consumer) ||
        dependency_producer.last_context.scene != &selection.scene_marker ||
        dependency_producer.last_context.camera != &selection.camera_marker ||
        dependency_producer.last_context.user_context != &selection ||
        dependency_producer.last_context.render_category_mask != 1u ||
        dependency_producer.last_context.layer_mask != 1u) {
        std::fprintf(stderr, "material enumeration lost the supplied selection context\n");
        return 1;
    }

    const size_t errors_before_missing_target = g_error_log_count;
    if (!tc_material_set_texture_source(dependency_material, "u_input", "render_target", "MissingTarget", "color") ||
        execute_plan(planner, topology, recorder) || find_target_job(recorder, consumer) ||
        !contains_diagnostic(recorder, OffscreenRenderDiagnosticKind::MissingMaterialTarget) ||
        g_error_log_count == errors_before_missing_target) {
        std::fprintf(stderr, "missing material target was not logged and rejected\n");
        return 1;
    }
    if (!tc_material_set_texture_source(dependency_material, "u_input", "render_target", "FovTarget", "color"))
        return 1;
    tc_render_target_set_enabled(producer, false);
    if (execute_plan(planner, topology, recorder) ||
        !contains_diagnostic(recorder, OffscreenRenderDiagnosticKind::DisabledDependency) ||
        find_target_job(recorder, producer) || find_target_job(recorder, consumer)) {
        std::fprintf(stderr, "disabled material target was not diagnosed and suppressed\n");
        return 1;
    }
    tc_render_target_set_enabled(producer, true);

    tc_component_detach_capability(&dependency_component, tc_drawable_capability_id());
    if (!tc_drawable_capability_attach(&dependency_component, &MISSING_ENUMERATION_VTABLE, &dependency_producer))
        return 1;
    const size_t errors_before_missing_callback = g_error_log_count;
    tc_render_item_collect_context missing_context{};
    tc_material_sink unused_sink{discard_material, nullptr};
    if (tc_component_collect_materials(&dependency_component, &missing_context, &unused_sink) ||
        g_error_log_count == errors_before_missing_callback) {
        std::fprintf(stderr, "missing material callback did not return false and log an error\n");
        return 1;
    }
    const size_t errors_before_failed_enumeration = g_error_log_count;
    if (execute_plan(planner, topology, recorder) || find_target_job(recorder, consumer) ||
        !contains_diagnostic(recorder, OffscreenRenderDiagnosticKind::MaterialEnumerationFailure) ||
        g_error_log_count == errors_before_failed_enumeration || dependency_producer.heavy_calls != 0) {
        std::fprintf(stderr, "missing material callback was not logged and rejected without heavy fallback\n");
        return 1;
    }
    tc_component_detach_capability(&dependency_component, tc_drawable_capability_id());
    if (!tc_drawable_capability_attach(&dependency_component, &DEPENDENCY_DRAWABLE_VTABLE, &dependency_producer))
        return 1;

    // Keep two independent consumer edges while recursively visiting a
    // producer with a different material set. Reusing the live enumeration
    // buffer across DFS would overwrite the second consumer edge here.
    tc_material_handle second_material = make_dependency_material("planner-material-second", "UnusedHiddenTarget");
    tc_material_handle nested_material = make_dependency_material("planner-material-nested", "UnattachedTarget");
    if (!tc_material_get(second_material) || !tc_material_get(nested_material))
        return 1;
    dependency_producer.materials[1] = second_material;
    dependency_producer.material_count = 2;
    DependencyProducer nested_producer;
    nested_producer.materials[0] = nested_material;
    nested_producer.material_count = 1;
    tc_entity_id nested_entity = tc_entity_pool_alloc(scene_pool, "nested-material-source-consumer");
    tc_entity_pool_set_layer(scene_pool, nested_entity, 1u);
    tc_component nested_component{};
    tc_component_init(&nested_component, nullptr);
    tc_entity_pool_add_component(scene_pool, nested_entity, &nested_component);
    if (!tc_drawable_capability_attach(&nested_component, &DEPENDENCY_DRAWABLE_VTABLE, &nested_producer) ||
        !execute_plan(planner, topology, recorder) || recorder.job_count != 4 ||
        target_job_index(recorder, unattached) >= target_job_index(recorder, producer) ||
        target_job_index(recorder, producer) >= target_job_index(recorder, consumer) ||
        target_job_index(recorder, unused) >= target_job_index(recorder, consumer) ||
        nested_producer.heavy_calls != 0 || dependency_producer.heavy_calls != 0) {
        std::fprintf(stderr, "nested DFS lost an independent consumer material dependency\n");
        return 1;
    }
    if (!tc_material_set_texture_source(tc_material_get(nested_material), "u_input", "render_target", "chronosquad", "color") ||
        execute_plan(planner, topology, recorder) ||
        !contains_diagnostic(recorder, OffscreenRenderDiagnosticKind::DependencyCycle) ||
        find_target_job(recorder, producer) || find_target_job(recorder, consumer)) {
        std::fprintf(stderr, "material-only dependency cycle was not diagnosed and suppressed\n");
        return 1;
    }
    tc_component_detach_capability(&nested_component, tc_drawable_capability_id());
    tc_entity_pool_remove_component(scene_pool, nested_entity, &nested_component);
    tc_material_destroy(nested_material);
    tc_material_destroy(second_material);
    tc_material_destroy(alternate_material);
    dependency_producer.material_count = 1;
    set_params(consumer, consumer_params, 3);
    tc_component_detach_capability(&dependency_component, tc_drawable_capability_id());
    tc_entity_pool_remove_component(scene_pool, dependency_entity, &dependency_component);

    const OffscreenRenderDemand debugger_demand{unused_viewport, unused};
    if (!execute_plan(planner, topology, recorder, active_display, &debugger_demand, 1) || recorder.job_count != 3 ||
        !find_target_job(recorder, unused) ||
        !tc_viewport_handle_eq(find_target_job(recorder, unused)->viewport, unused_viewport) ||
        target_job_index(recorder, producer) >= target_job_index(recorder, consumer)) {
        std::fprintf(stderr, "debugger demand did not activate hidden target with dependency closure\n");
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
    if (!editor_topology.register_viewport(scene, editor_viewport, editor_display, false) ||
        !execute_plan(planner, editor_topology, recorder, editor_display) || recorder.job_count != 1 ||
        !find_target_job(recorder, editor_target) ||
        !tc_viewport_handle_eq(recorder.jobs[0].viewport, editor_viewport)) {
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
    if (execute_plan(planner, topology, recorder) ||
        !contains_diagnostic(recorder, OffscreenRenderDiagnosticKind::DependencyCycle) ||
        find_target_job(recorder, producer) || find_target_job(recorder, consumer)) {
        std::fprintf(stderr, "dependency cycle was not diagnosed and suppressed\n");
        return 1;
    }

    tc_scene_handle atomic_scene = tc_scene_new_named("atomic-pipeline-test");
    const char* atomic_targets[] = {"atomic_active", "atomic_hidden"};
    TestPipeline atomic_pipeline =
        make_pipeline("render-frame-planner-atomic", "AtomicPipeline", nullptr, 0, atomic_targets, 2);
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
    if (!tc_scene_add_pipeline_template(atomic_scene, atomic_pipeline.pipeline_template) ||
        !atomic_topology.attach_scene(atomic_scene) || !execute_plan(planner, atomic_topology, recorder) ||
        recorder.job_count != 1 || recorder.jobs[0].kind != OffscreenRenderJobKind::ScenePipeline ||
        atomic_topology.pipeline_target_count(atomic_scene, recorder.jobs[0].pipeline) != 2) {
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
    tc_material_destroy(g_dependency_material);
    tc_log_set_callback(nullptr);
    tc_scene_free(scene);
    tc_material_shutdown();
    tc_scene_ext_registry_shutdown();
    tc_pipeline_template_shutdown();
    tc_display_pool_shutdown();
    return 0;
}
