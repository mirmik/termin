#include "render_frame_planner.hpp"

#include "pipeline_texture_ref.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <new>
#include <vector>

extern "C" {
#include <tcbase/tc_log.h>
#include "render/tc_pipeline_template_registry.h"
#include "render/tc_render_surface.h"
}

namespace termin::rendering_manager_detail {

namespace {

constexpr uint32_t INVALID_JOB_INDEX = std::numeric_limits<uint32_t>::max();

enum VisitState : uint8_t {
    VISIT_UNVISITED,
    VISIT_VISITING,
    VISIT_COMPLETE,
    VISIT_FAILED,
};

struct ProducerEntry {
    tc_render_target_handle target = TC_RENDER_TARGET_HANDLE_INVALID;
    uint32_t job = INVALID_JOB_INDEX;
};

bool starts_with_external(const char* resource_type) {
    return resource_type && std::strncmp(resource_type, "external", 8) == 0;
}

const char* target_name(tc_render_target_handle target) {
    const char* name = tc_render_target_get_name(target);
    return name && name[0] ? name : "<unnamed>";
}

bool viewport_is_demanded(
    tc_viewport_handle viewport,
    const OffscreenRenderDemand* demands,
    size_t demand_count
) {
    for (size_t i = 0; i < demand_count; ++i) {
        if (tc_viewport_handle_eq(demands[i].viewport, viewport)) return true;
    }
    return false;
}

void log_job(const char* prefix, const OffscreenRenderJob& job) {
    if (job.kind == OffscreenRenderJobKind::ScenePipeline) {
        tc_log(
            TC_LOG_ERROR,
            "[RenderingManager] %s scene pipeline [%u:%u]",
            prefix,
            job.pipeline.index,
            job.pipeline.generation
        );
        return;
    }
    tc_log(
        TC_LOG_ERROR,
        "[RenderingManager] %s render target '%s' [%u:%u]",
        prefix,
        target_name(job.render_target),
        job.render_target.index,
        job.render_target.generation
    );
}

} // namespace

struct OffscreenRenderPlanner::Impl {
    // Persistent scratch: clear() keeps capacity, so the steady-state frame
    // performs no scheduler container allocations.
    std::vector<OffscreenRenderJob> jobs;
    std::vector<ProducerEntry> producers;
    std::vector<uint8_t> roots;
    std::vector<uint8_t> states;
    std::vector<uint32_t> stack;
    std::vector<const char*> pass_reads;

    const RenderTopology* topology = nullptr;
    OffscreenRenderJobCallback job_callback = nullptr;
    void* job_user_data = nullptr;
    OffscreenRenderDiagnosticCallback diagnostic_callback = nullptr;
    void* diagnostic_user_data = nullptr;
    bool had_error = false;

    void emit(const OffscreenRenderDiagnostic& diagnostic) {
        had_error = true;
        if (diagnostic_callback) {
            diagnostic_callback(diagnostic_user_data, &diagnostic);
        }
    }

    bool prepare_job_scratch(size_t count) {
        roots.resize(count);
        states.resize(count);
        std::fill(roots.begin(), roots.end(), 0);
        std::fill(states.begin(), states.end(), VISIT_UNVISITED);
        stack.clear();
        stack.reserve(count);
        return true;
    }

    uint32_t append_job(const OffscreenRenderJob& job) {
        if (jobs.size() >= INVALID_JOB_INDEX) return INVALID_JOB_INDEX;
        const uint32_t index = static_cast<uint32_t>(jobs.size());
        jobs.push_back(job);
        return index;
    }

    uint32_t producer_for(tc_render_target_handle target) const {
        for (const ProducerEntry& producer : producers) {
            if (tc_render_target_handle_eq(producer.target, target)) {
                return producer.job;
            }
        }
        return INVALID_JOB_INDEX;
    }

    bool register_producer(tc_render_target_handle target, uint32_t job) {
        if (!tc_render_target_handle_valid(target)) return true;
        const uint32_t previous = producer_for(target);
        if (previous != INVALID_JOB_INDEX) {
            tc_log(
                TC_LOG_ERROR,
                "[RenderingManager] render target '%s' has more than one producer job",
                target_name(target)
            );
            emit({OffscreenRenderDiagnosticKind::DuplicateProducer, target, job, previous});
            return false;
        }
        producers.push_back({target, job});
        return true;
    }

    bool ensure_render_target_job(tc_render_target_handle target) {
        if (!tc_render_target_handle_valid(target)
                || producer_for(target) != INVALID_JOB_INDEX) {
            return true;
        }
        const uint32_t job = append_job({
            OffscreenRenderJobKind::RenderTarget,
            tc_render_target_get_scene(target),
            target,
            TC_VIEWPORT_HANDLE_INVALID,
            tc_render_target_get_pipeline(target),
        });
        if (job == INVALID_JOB_INDEX) return false;
        return register_producer(target, job);
    }

    size_t output_count(const OffscreenRenderJob& job) const {
        return job.kind == OffscreenRenderJobKind::RenderTarget
            ? 1 : topology->pipeline_target_count(job.scene, job.pipeline);
    }

    tc_render_target_handle output_at(const OffscreenRenderJob& job, size_t index) const {
        if (job.kind == OffscreenRenderJobKind::RenderTarget) {
            return index == 0 ? job.render_target : TC_RENDER_TARGET_HANDLE_INVALID;
        }
        tc_viewport_handle viewport = topology->pipeline_target_viewport_at(
            job.scene, job.pipeline, index);
        return tc_viewport_handle_valid(viewport)
            ? tc_viewport_get_render_target(viewport) : TC_RENDER_TARGET_HANDLE_INVALID;
    }

    bool pipeline_uses_external_slot(tc_pipeline_handle pipeline, const char* slot) {
        if (!tc_pipeline_handle_valid(pipeline) || !slot || slot[0] == '\0') return false;

        const tc_pipeline_template* pipeline_template = tc_pipeline_template_get(
            tc_pipeline_get_template(pipeline));
        if (pipeline_template) {
            for (uint32_t i = 0; i < pipeline_template->resource_count; ++i) {
                const tc_pipeline_template_resource_desc& resource =
                    pipeline_template->resources[i];
                if (resource.name && std::strcmp(resource.name, slot) == 0
                        && starts_with_external(resource.resource_type)) {
                    return true;
                }
            }
            return false;
        }

        const size_t pass_count = tc_pipeline_pass_count(pipeline);
        for (size_t pass_index = 0; pass_index < pass_count; ++pass_index) {
            tc_pass* pass = tc_pipeline_get_pass_at(pipeline, pass_index);
            if (!pass || !pass->enabled) continue;
            const size_t read_count = tc_pass_get_reads(pass, nullptr, 0);
            pass_reads.resize(read_count);
            const size_t actual = tc_pass_get_reads(pass, pass_reads.data(), read_count);
            const size_t available = actual < read_count ? actual : read_count;
            for (size_t i = 0; i < available; ++i) {
                if (pass_reads[i] && std::strcmp(pass_reads[i], slot) == 0) return true;
            }
        }
        return false;
    }

    bool visit(uint32_t index) {
        if (states[index] == VISIT_COMPLETE) return true;
        if (states[index] == VISIT_FAILED) return false;
        if (states[index] == VISIT_VISITING) {
            size_t cycle_begin = 0;
            while (cycle_begin < stack.size() && stack[cycle_begin] != index) ++cycle_begin;
            tc_log(TC_LOG_ERROR, "[RenderingManager] render dependency cycle:");
            for (size_t i = cycle_begin; i < stack.size(); ++i) {
                states[stack[i]] = VISIT_FAILED;
                log_job("cycle member", jobs[stack[i]]);
            }
            log_job("cycle closes at", jobs[index]);
            emit({OffscreenRenderDiagnosticKind::DependencyCycle,
                  TC_RENDER_TARGET_HANDLE_INVALID, index, index});
            return false;
        }

        states[index] = VISIT_VISITING;
        stack.push_back(index);
        bool valid = true;
        const OffscreenRenderJob& consumer = jobs[index];
        const size_t outputs = output_count(consumer);
        for (size_t output_index = 0; output_index < outputs; ++output_index) {
            const tc_render_target_handle output = output_at(consumer, output_index);
            if (!tc_render_target_handle_valid(output)) continue;
            const tc_value* params = tc_render_target_get_pipeline_params(output);
            if (!params || params->type != TC_VALUE_DICT) continue;
            for (size_t param_index = 0; param_index < params->data.dict.count; ++param_index) {
                const char* slot = params->data.dict.entries[param_index].key;
                const tc_value* value = params->data.dict.entries[param_index].value;
                if (!slot || !value || value->type != TC_VALUE_STRING
                        || !pipeline_uses_external_slot(consumer.pipeline, slot)) {
                    continue;
                }
                const PipelineTextureRef ref = classify_pipeline_texture_ref(
                    value->data.s,
                    tc_render_target_get_scene(output),
                    topology->managed_render_target_data(),
                    topology->managed_render_target_count());
                if (ref.kind != PipelineTextureRefKind::RenderTarget) continue;
                const uint32_t producer = producer_for(ref.render_target);
                if (producer == INVALID_JOB_INDEX) continue;
                if (!tc_render_target_get_enabled(ref.render_target)) {
                    tc_log(
                        TC_LOG_ERROR,
                        "[RenderingManager] render job depends on disabled target '%s'",
                        target_name(ref.render_target)
                    );
                    emit({OffscreenRenderDiagnosticKind::DisabledDependency,
                          ref.render_target, index, producer});
                    valid = false;
                    continue;
                }
                if (!visit(producer)) valid = false;
            }
        }
        stack.pop_back();

        if (!valid || states[index] == VISIT_FAILED) {
            states[index] = VISIT_FAILED;
            return false;
        }
        states[index] = VISIT_COMPLETE;
        if (job_callback) job_callback(job_user_data, &jobs[index]);
        return true;
    }

    bool execute(
        const RenderTopology& source_topology,
        tc_display_handle only_display,
        OffscreenRenderJobCallback callback,
        void* callback_user_data,
        OffscreenRenderDiagnosticCallback diagnostics,
        void* diagnostics_user_data,
        const OffscreenRenderDemand* demands,
        size_t demand_count
    ) {
        topology = &source_topology;
        job_callback = callback;
        job_user_data = callback_user_data;
        diagnostic_callback = diagnostics;
        diagnostic_user_data = diagnostics_user_data;
        had_error = false;
        jobs.clear();
        producers.clear();

        for (size_t scene_index = 0; scene_index < topology->attached_scene_count(); ++scene_index) {
            const tc_scene_handle scene = topology->attached_scene_at(scene_index);
            if (!tc_scene_alive(scene)) continue;
            for (size_t pipeline_index = 0;
                 pipeline_index < topology->pipeline_count(scene);
                 ++pipeline_index) {
                const tc_pipeline_handle pipeline = topology->pipeline_at(scene, pipeline_index);
                if (!tc_pipeline_handle_valid(pipeline)) continue;
                const uint32_t job = append_job({
                    OffscreenRenderJobKind::ScenePipeline,
                    scene,
                    TC_RENDER_TARGET_HANDLE_INVALID,
                    TC_VIEWPORT_HANDLE_INVALID,
                    pipeline,
                });
                if (job == INVALID_JOB_INDEX) return false;
                const size_t outputs = topology->pipeline_target_count(scene, pipeline);
                for (size_t output_index = 0; output_index < outputs; ++output_index) {
                    const tc_viewport_handle viewport = topology->pipeline_target_viewport_at(
                        scene, pipeline, output_index);
                    if (tc_viewport_handle_valid(viewport)) {
                        register_producer(tc_viewport_get_render_target(viewport), job);
                    }
                }
            }
        }

        for (size_t i = 0; i < topology->managed_render_target_count(); ++i) {
            const tc_render_target_handle target = topology->managed_render_target_at(i);
            if (!ensure_render_target_job(target)) return false;
        }

        // Host/editor attachments may point to externally owned render
        // targets. They participate in scheduling without being adopted into
        // managed_render_targets (which would incorrectly transfer lifetime).
        for (size_t i = 0; i < topology->viewport_attachment_count(); ++i) {
            const RenderTopology::ViewportAttachment* attachment =
                topology->viewport_attachment_at(i);
            if (!attachment || !tc_viewport_handle_valid(attachment->viewport)) continue;
            if (!ensure_render_target_job(
                    tc_viewport_get_render_target(attachment->viewport))) {
                return false;
            }
        }

        prepare_job_scratch(jobs.size());

        for (size_t i = 0; i < topology->viewport_attachment_count(); ++i) {
            const RenderTopology::ViewportAttachment* attachment =
                topology->viewport_attachment_at(i);
            if (!attachment || !tc_viewport_handle_valid(attachment->viewport)) continue;
            const tc_render_target_handle target = tc_viewport_get_render_target(attachment->viewport);
            const uint32_t producer = producer_for(target);
            if (producer == INVALID_JOB_INDEX) continue;

            const bool selected_display = !tc_display_handle_valid(only_display)
                || tc_display_handle_eq(attachment->display, only_display);
            if (!selected_display || !tc_display_alive(attachment->display)
                    || !tc_display_get_enabled(attachment->display)
                    || !tc_viewport_get_enabled(attachment->viewport)
                    || !tc_render_target_get_enabled(target)) {
                continue;
            }
            roots[producer] = 1;
            if (jobs[producer].kind == OffscreenRenderJobKind::RenderTarget
                    && !tc_viewport_handle_valid(jobs[producer].viewport)) {
                jobs[producer].viewport = attachment->viewport;
            }
        }

        for (size_t i = 0; i < demand_count; ++i) {
            const OffscreenRenderDemand& demand = demands[i];
            const tc_render_target_handle target = demand.render_target;
            if (!tc_render_target_alive(target) || !tc_render_target_get_enabled(target)) {
                continue;
            }
            if (tc_viewport_handle_valid(demand.viewport)) {
                if (!tc_viewport_alive(demand.viewport)
                        || !tc_viewport_get_enabled(demand.viewport)
                        || !tc_render_target_handle_eq(
                            tc_viewport_get_render_target(demand.viewport), target)) {
                    continue;
                }
            }
            const uint32_t producer = producer_for(target);
            if (producer == INVALID_JOB_INDEX) continue;
            roots[producer] = 1;
            if (jobs[producer].kind == OffscreenRenderJobKind::RenderTarget
                    && tc_viewport_handle_valid(demand.viewport)) {
                jobs[producer].viewport = demand.viewport;
            }
        }

        for (uint32_t i = 0; i < jobs.size(); ++i) {
            if (roots[i]) visit(i);
        }
        return !had_error;
    }
};

OffscreenRenderPlanner::OffscreenRenderPlanner()
    : impl_(new (std::nothrow) Impl()) {
    if (!impl_) {
        tc_log(TC_LOG_ERROR, "[RenderingManager] failed to allocate offscreen planner");
    }
}

OffscreenRenderPlanner::~OffscreenRenderPlanner() {
    delete impl_;
}

bool OffscreenRenderPlanner::execute(
    const RenderTopology& topology,
    tc_display_handle only_display,
    OffscreenRenderJobCallback job_callback,
    void* job_user_data,
    OffscreenRenderDiagnosticCallback diagnostic_callback,
    void* diagnostic_user_data,
    const OffscreenRenderDemand* demands,
    size_t demand_count
) {
    if (!impl_) return false;
    try {
        return impl_->execute(
            topology,
            only_display,
            job_callback,
            job_user_data,
            diagnostic_callback,
            diagnostic_user_data,
            demands,
            demand_count);
    } catch (const std::bad_alloc&) {
        tc_log(TC_LOG_ERROR, "[RenderingManager] offscreen planner scratch allocation failed");
        if (diagnostic_callback) {
            const OffscreenRenderDiagnostic diagnostic{
                OffscreenRenderDiagnosticKind::AllocationFailure};
            diagnostic_callback(diagnostic_user_data, &diagnostic);
        }
        return false;
    }
}

void update_viewport_rects(
    const RenderTopology& topology,
    tc_display_handle only_display,
    const OffscreenRenderDemand* demands,
    size_t demand_count
) {
    for (size_t i = 0; i < topology.viewport_attachment_count(); ++i) {
        const RenderTopology::ViewportAttachment* attachment = topology.viewport_attachment_at(i);
        if (!attachment) continue;
        const tc_display_handle display = attachment->display;
        const bool demanded = viewport_is_demanded(
            attachment->viewport, demands, demand_count);
        if (!tc_display_alive(display)
                || (!demanded && tc_display_handle_valid(only_display)
                    && !tc_display_handle_eq(display, only_display))
                || (!demanded && !tc_display_get_enabled(display))) {
            continue;
        }
        tc_render_surface* surface = tc_display_get_surface(display);
        if (!surface) continue;
        int width = 0;
        int height = 0;
        tc_render_surface_get_size(surface, &width, &height);
        if (width > 0 && height > 0 && tc_viewport_handle_valid(attachment->viewport)) {
            tc_viewport_update_pixel_rect(attachment->viewport, width, height);
        }
    }
}

void sync_viewport_render_target_resolutions(
    const RenderTopology& topology,
    tc_display_handle only_display,
    const OffscreenRenderDemand* demands,
    size_t demand_count
) {
    for (size_t i = 0; i < topology.viewport_attachment_count(); ++i) {
        const RenderTopology::ViewportAttachment* attachment = topology.viewport_attachment_at(i);
        if (!attachment) continue;
        const tc_display_handle display = attachment->display;
        const bool demanded = viewport_is_demanded(
            attachment->viewport, demands, demand_count);
        if (!tc_display_alive(display)
                || (!demanded && tc_display_handle_valid(only_display)
                    && !tc_display_handle_eq(display, only_display))
                || (!demanded && !tc_display_get_enabled(display))) {
            continue;
        }
        const tc_viewport_handle viewport = attachment->viewport;
        if (!tc_viewport_handle_valid(viewport) || !tc_viewport_get_enabled(viewport)) continue;
        const tc_render_target_handle target = tc_viewport_get_render_target(viewport);
        if (!tc_render_target_handle_valid(target)
                || !tc_render_target_get_enabled(target)
                || tc_render_target_get_kind(target) != TC_RENDER_TARGET_TEXTURE_2D
                || !tc_render_target_get_dynamic_resolution(target)) {
            continue;
        }
        int x = 0;
        int y = 0;
        int width = 0;
        int height = 0;
        tc_viewport_get_pixel_rect(viewport, &x, &y, &width, &height);
        if (width > 0 && height > 0) {
            tc_render_target_set_width(target, width);
            tc_render_target_set_height(target, height);
        }
    }
}

} // namespace termin::rendering_manager_detail
