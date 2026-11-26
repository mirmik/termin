#include "render_frame_planner.hpp"

#include "pipeline_texture_ref.hpp"
#include "termin/render/frame_graph_capture.hpp"
#include "termin/render/render_pipeline.hpp"
#include "termin/render/render_scene_item_collector.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <new>
#include <unordered_map>
#include <vector>

extern "C" {
#include "render/tc_render_surface.h"
#include "tgfx/resources/tc_material_registry.h"
#include <tcbase/tc_log.h>
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

        uint64_t target_key(tc_render_target_handle target) {
            return (static_cast<uint64_t>(target.generation) << 32) | target.index;
        }

        struct OutputStamp {
            uint64_t target;
            uint64_t revision;
            bool enabled;

            bool operator==(const OutputStamp&) const = default;
        };

        OutputStamp output_stamp(tc_render_target_handle target) {
            return {target_key(target), tc_render_target_render_revision(target), tc_render_target_get_enabled(target)};
        }

        struct CachedJob {
            tc_scene_handle scene;
            tc_pipeline_handle pipeline;
            tc_viewport_handle viewport;
            uint64_t scene_revision;
            uint64_t pipeline_revision;
            std::vector<OutputStamp> outputs;
            std::vector<tc_render_target_handle> dependencies;
            bool invalidated = false;
            uint64_t content_revision = 0;
        };

        const char* target_name(tc_render_target_handle target) {
            const char* name = tc_render_target_get_name(target);
            return name && name[0] ? name : "<unnamed>";
        }

        bool
        viewport_is_demanded(tc_viewport_handle viewport, const OffscreenRenderDemand* demands, size_t demand_count) {
            for (size_t i = 0; i < demand_count; ++i) {
                if (tc_viewport_handle_eq(demands[i].viewport, viewport))
                    return true;
            }
            return false;
        }

        void log_job(const char* prefix, const OffscreenRenderJob& job) {
            if (job.kind == OffscreenRenderJobKind::ScenePipeline) {
                tc_log(TC_LOG_ERROR,
                       "[RenderingManager] %s scene pipeline [%u:%u]",
                       prefix,
                       job.pipeline.index,
                       job.pipeline.generation);
                return;
            }
            tc_log(TC_LOG_ERROR,
                   "[RenderingManager] %s render target '%s' [%u:%u]",
                   prefix,
                   target_name(job.render_target),
                   job.render_target.index,
                   job.render_target.generation);
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
        // Frame-local edges: retain capacity, index ranges survive nested DFS.
        std::vector<tc_render_target_handle> dependency_edges;
        std::unordered_map<uint64_t, CachedJob> cached_jobs;
        std::vector<uint64_t> cache_keys;
        std::vector<const char*> dirty_reasons;
        std::vector<std::vector<uint32_t>> consumers;
        std::vector<uint32_t> dirty_jobs;
        const OffscreenRenderCacheOptions* cache_options = nullptr;
        uint64_t content_revision = 0;
        OffscreenMaterialDependencyCallback material_callback = nullptr;
        void* material_user_data = nullptr;

        const RenderTopology* topology = nullptr;
        OffscreenRenderJobCallback job_callback = nullptr;
        OffscreenRenderCaptureCallbacks capture_callbacks;
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
            if (jobs.size() >= INVALID_JOB_INDEX)
                return INVALID_JOB_INDEX;
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
            if (!tc_render_target_handle_valid(target))
                return true;
            const uint32_t previous = producer_for(target);
            if (previous != INVALID_JOB_INDEX) {
                tc_log(TC_LOG_ERROR,
                       "[RenderingManager] render target '%s' has more than one producer job",
                       target_name(target));
                emit({OffscreenRenderDiagnosticKind::DuplicateProducer, target, job, previous});
                return false;
            }
            producers.push_back({target, job});
            return true;
        }

        bool ensure_render_target_job(tc_render_target_handle target) {
            if (!tc_render_target_handle_valid(target) || producer_for(target) != INVALID_JOB_INDEX) {
                return true;
            }
            const uint32_t job = append_job({
                OffscreenRenderJobKind::RenderTarget,
                tc_render_target_get_scene(target),
                target,
                TC_VIEWPORT_HANDLE_INVALID,
                tc_render_target_get_pipeline(target),
            });
            if (job == INVALID_JOB_INDEX)
                return false;
            return register_producer(target, job);
        }

        size_t output_count(const OffscreenRenderJob& job) const {
            return job.kind == OffscreenRenderJobKind::RenderTarget
                       ? 1
                       : topology->pipeline_target_count(job.scene, job.pipeline);
        }

        tc_render_target_handle output_at(const OffscreenRenderJob& job, size_t index) const {
            if (job.kind == OffscreenRenderJobKind::RenderTarget) {
                return index == 0 ? job.render_target : TC_RENDER_TARGET_HANDLE_INVALID;
            }
            tc_viewport_handle viewport = topology->pipeline_target_viewport_at(job.scene, job.pipeline, index);
            return tc_viewport_handle_valid(viewport) ? tc_viewport_get_render_target(viewport)
                                                      : TC_RENDER_TARGET_HANDLE_INVALID;
        }

        uint64_t cache_key(const OffscreenRenderJob& job) const {
            for (size_t i = 0; i < output_count(job); ++i) {
                const auto target = output_at(job, i);
                if (tc_render_target_alive(target))
                    return target_key(target);
            }
            return target_key(TC_RENDER_TARGET_HANDLE_INVALID);
        }

        const char* invalidation_reason(const OffscreenRenderJob& job, const CachedJob& cached) const {
            if (!tc_scene_handle_eq(job.scene, cached.scene) ||
                !tc_pipeline_handle_eq(job.pipeline, cached.pipeline) ||
                !tc_viewport_handle_eq(job.viewport, cached.viewport) ||
                tc_pipeline_render_revision(job.pipeline) != cached.pipeline_revision ||
                output_count(job) != cached.outputs.size()) {
                return "pipeline or attachment change";
            }
            if (tc_scene_get_mode(job.scene) == TC_SCENE_MODE_PLAY)
                return "scene playback";
            if (tc_scene_render_revision(job.scene) != cached.scene_revision)
                return "scene request";
            for (size_t i = 0; i < cached.outputs.size(); ++i) {
                const auto target = output_at(job, i);
                if (!(output_stamp(target) == cached.outputs[i]))
                    return "target request";
                if (cached.outputs[i].enabled &&
                     (tc_render_target_get_kind(target) != TC_RENDER_TARGET_TEXTURE_2D ||
                      (cache_options->has_output && !cache_options->has_output(target)))) {
                    return "missing or transient output";
                }
            }
            return cached.invalidated ? "pending dependency change" : nullptr;
        }

        void mark_dirty(uint32_t index, const char* reason) {
            if (!dirty_reasons[index]) {
                dirty_reasons[index] = reason;
                dirty_jobs.push_back(index);
            }
        }

        void select_dirty_jobs() {
            if (cache_options->force)
                cached_jobs.clear();
            cache_keys.resize(jobs.size());
            dirty_reasons.assign(jobs.size(), nullptr);
            consumers.resize(jobs.size());
            for (auto& edges : consumers)
                edges.clear();
            dirty_jobs.clear();
            for (uint32_t i = 0; i < jobs.size(); ++i) {
                const auto key = cache_key(jobs[i]);
                cache_keys[i] = key;
                const auto cached = cached_jobs.find(key);
                if (cached == cached_jobs.end()) {
                    mark_dirty(i, cache_options->force ? "global request" : "initial output");
                    continue;
                }
                if (const char* reason = invalidation_reason(jobs[i], cached->second))
                    mark_dirty(i, reason);
                for (const auto dependency : cached->second.dependencies) {
                    const uint32_t producer = producer_for(dependency);
                    if (producer == INVALID_JOB_INDEX || !tc_render_target_get_enabled(dependency)) {
                        mark_dirty(i, "missing or disabled dependency");
                    } else {
                        consumers[producer].push_back(i);
                    }
                }
            }
            std::erase_if(cached_jobs, [this](const auto& entry) {
                return std::find(cache_keys.begin(), cache_keys.end(), entry.first) == cache_keys.end();
            });
        }

        tc_render_target_handle find_scene_render_target(tc_scene_handle scene, const char* name) const {
            if (!name || !name[0])
                return TC_RENDER_TARGET_HANDLE_INVALID;
            for (size_t i = 0; i < topology->managed_render_target_count(); ++i) {
                const tc_render_target_handle target = topology->managed_render_target_at(i);
                if (!tc_render_target_alive(target) ||
                    !tc_scene_handle_eq(tc_render_target_get_scene(target), scene)) {
                    continue;
                }
                const char* candidate_name = tc_render_target_get_name(target);
                if (candidate_name && std::strcmp(candidate_name, name) == 0)
                    return target;
            }
            return TC_RENDER_TARGET_HANDLE_INVALID;
        }

        bool visit_render_target_dependency(tc_render_target_handle dependency,
                                            uint32_t consumer_index,
                                            bool& valid) {
            const uint32_t producer = producer_for(dependency);
            if (producer == INVALID_JOB_INDEX)
                return true;
            if (!tc_render_target_get_enabled(dependency)) {
                tc_log(TC_LOG_ERROR,
                       "[RenderingManager] render job depends on disabled target '%s'",
                       target_name(dependency));
                emit({OffscreenRenderDiagnosticKind::DisabledDependency, dependency, consumer_index, producer});
                valid = false;
                return false;
            }
            if (!visit(producer)) {
                valid = false;
                return false;
            }
            return true;
        }

        struct MaterialEdgeContext {
            Impl* planner;
            tc_scene_handle scene;
            uint32_t consumer;
            bool valid = true;
        };

        static bool emit_material_edge(tc_material_handle handle, void* user_data) {
            auto& context = *static_cast<MaterialEdgeContext*>(user_data);
            const tc_material* material = tc_material_get(handle);
            if (!material) {
                tc_log(TC_LOG_ERROR, "[RenderingManager] drawable enumerated a stale material handle");
                context.valid = false;
                return false;
            }
            for (size_t i = 0; i < material->texture_source_count; ++i) {
                const tc_material_texture_source& source = material->texture_sources[i];
                if (std::strcmp(source.kind, "render_target") != 0)
                    continue;
                const auto dependency = context.planner->find_scene_render_target(context.scene, source.source_name);
                if (!tc_render_target_handle_valid(dependency)) {
                    tc_log(TC_LOG_ERROR, "[RenderingManager] material '%s' references missing render target '%s'",
                           material->header.name ? material->header.name : "<unnamed>", source.source_name);
                    context.planner->emit({OffscreenRenderDiagnosticKind::MissingMaterialTarget,
                                          TC_RENDER_TARGET_HANDLE_INVALID, context.consumer});
                    context.valid = false;
                    continue;
                }
                context.planner->dependency_edges.push_back(dependency);
            }
            return true;
        }

        void collect_material_dependencies(tc_render_target_handle output, uint32_t consumer_index, bool& valid) {
            MaterialEdgeContext context{this, tc_render_target_get_scene(output), consumer_index};
            tc_material_sink sink{emit_material_edge, &context};
            bool collected = false;
            if (material_callback) {
                collected = material_callback(material_user_data, &jobs[consumer_index], output, &sink);
            } else {
                // Headless planner clients have no target view provider. Runtime
                // manager always supplies the prepared execution context above.
                RenderSceneItemCollectRequest request;
                request.scene = context.scene;
                request.flags = TC_RENDER_ITEM_COLLECT_FLAG_ALLOW_MISSING_MATERIAL_PHASE;
                request.layer_mask = tc_render_target_get_layer_mask(output);
                request.debug_pass_name = "MaterialTextureDependencyPlanner";
                collected = collect_scene_materials(request, sink);
            }
            if (!collected || !context.valid) {
                tc_log(TC_LOG_ERROR, "[RenderingManager] failed to enumerate material dependencies for target '%s'",
                       target_name(output));
                emit({OffscreenRenderDiagnosticKind::MaterialEnumerationFailure, output, consumer_index});
                valid = false;
            }
        }

        void collect_pipeline_dependencies(tc_render_target_handle output, const FrameGraphSchedule& schedule) {
            const tc_value* params = tc_render_target_get_pipeline_params(output);
            if (!params || params->type != TC_VALUE_DICT)
                return;
            for (size_t i = 0; i < params->data.dict.count; ++i) {
                const char* slot = params->data.dict.entries[i].key;
                const tc_value* value = params->data.dict.entries[i].value;
                if (!slot || !value || value->type != TC_VALUE_STRING || !schedule.resources.contains(slot))
                    continue;
                const PipelineTextureRef ref = classify_pipeline_texture_ref(value->data.s,
                    tc_render_target_get_scene(output), topology->managed_render_target_data(),
                    topology->managed_render_target_count());
                if (ref.kind == PipelineTextureRefKind::RenderTarget)
                    dependency_edges.push_back(ref.render_target);
            }
        }

        bool visit(uint32_t index) {
            if (states[index] == VISIT_COMPLETE)
                return true;
            if (states[index] == VISIT_FAILED)
                return false;
            if (cache_options && !dirty_reasons[index])
                return true;
            if (states[index] == VISIT_VISITING) {
                size_t cycle_begin = 0;
                while (cycle_begin < stack.size() && stack[cycle_begin] != index)
                    ++cycle_begin;
                tc_log(TC_LOG_ERROR, "[RenderingManager] render dependency cycle:");
                for (size_t i = cycle_begin; i < stack.size(); ++i) {
                    states[stack[i]] = VISIT_FAILED;
                    log_job("cycle member", jobs[stack[i]]);
                }
                log_job("cycle closes at", jobs[index]);
                emit({OffscreenRenderDiagnosticKind::DependencyCycle, TC_RENDER_TARGET_HANDLE_INVALID, index, index});
                return false;
            }

            states[index] = VISIT_VISITING;
            stack.push_back(index);
            bool valid = true;
            const OffscreenRenderJob& consumer = jobs[index];
            static const bool trace = std::getenv("TERMIN_TRACE_RENDER_SCHEDULER") != nullptr;
            if (cache_options && trace) {
                tc_log(TC_LOG_INFO, "[RenderScheduler] %s '%s' (scene %u:%u, pipeline %u:%u): %s",
                       roots[index] ? "root" : "producer", target_name(output_at(consumer, 0)),
                       consumer.scene.index, consumer.scene.generation,
                       consumer.pipeline.index, consumer.pipeline.generation, dirty_reasons[index]);
            }
            const size_t edge_begin = dependency_edges.size();
            const size_t outputs = output_count(consumer);
            CachedJob next{consumer.scene, consumer.pipeline, consumer.viewport,
                           tc_scene_render_revision(consumer.scene), 0, {}, {}};
            if (cache_options) {
                next.outputs.reserve(outputs);
                for (size_t i = 0; i < outputs; ++i)
                    next.outputs.push_back(output_stamp(output_at(consumer, i)));
            }
            for (size_t output_index = 0; output_index < outputs; ++output_index) {
                const tc_render_target_handle output = output_at(consumer, output_index);
                if (tc_render_target_alive(output) && tc_render_target_get_enabled(output))
                    collect_material_dependencies(output, index, valid);
            }

            OffscreenRenderExecution execution;
            if (valid) {
                if (capture_callbacks.prepare)
                    capture_callbacks.prepare(job_user_data, &consumer, execution.captures);
                RenderPipeline pipeline(consumer.pipeline);
                tc_frame_graph* graph = tc_pipeline_get_frame_graph(consumer.pipeline);
                if (!graph || tc_frame_graph_get_error(graph) != TC_FG_OK) {
                    log_job("cannot select frame graph for", consumer);
                    if (const char* error = tc_frame_graph_get_error_message(graph))
                        tc_log(TC_LOG_ERROR, "[RenderingManager] %s", error);
                    valid = false;
                } else {
                    execution.schedule = select_frame_graph_schedule(pipeline, graph, execution.captures);
                    valid = execution.schedule.valid;
                    next.pipeline_revision = execution.schedule.pipeline_revision;
                }
            }
            if (valid) {
                for (size_t i = 0; i < outputs; ++i) {
                    const auto output = output_at(consumer, i);
                    if (tc_render_target_alive(output) && tc_render_target_get_enabled(output))
                        collect_pipeline_dependencies(output, execution.schedule);
                }
            }
            const size_t edge_end = dependency_edges.size();
            if (valid) {
                for (size_t edge = edge_begin; edge < edge_end; ++edge) {
                    // Copy before recursion: nested enumeration can grow the vector.
                    const auto dependency = dependency_edges[edge];
                    visit_render_target_dependency(dependency, index, valid);
                }
            }
            stack.pop_back();

            if (valid && !execution.schedule.matches(consumer.pipeline)) {
                log_job("pipeline changed while resolving dependencies for", consumer);
                valid = false;
            }
            valid = valid && states[index] != VISIT_FAILED;
            if (valid && job_callback)
                valid = job_callback(job_user_data, &consumer, execution);
            if (!execution.captures.empty() && capture_callbacks.finish) {
                for (auto* capture : execution.captures) {
                    if (capture && capture->status == FrameGraphCaptureRequestStatus::Pending)
                        capture->status = FrameGraphCaptureRequestStatus::ResourceUnavailable;
                }
                capture_callbacks.finish(job_user_data, &consumer, execution.captures);
            }
            if (!valid) {
                states[index] = VISIT_FAILED;
                had_error = true;
                if (cache_options)
                    cached_jobs.erase(cache_keys[index]);
                return false;
            }
            states[index] = VISIT_COMPLETE;
            if (cache_options) {
                // A capture can add temporary reads. Publish its output but
                // derive the next ordinary frame's edges from a fresh schedule.
                next.invalidated = !execution.captures.empty();
                if (!next.invalidated)
                    next.dependencies.assign(dependency_edges.begin() + edge_begin, dependency_edges.begin() + edge_end);
                next.content_revision = ++content_revision;
                cached_jobs.insert_or_assign(cache_keys[index], std::move(next));
            }
            return true;
        }

        bool execute(const RenderTopology& source_topology,
                     tc_display_handle only_display,
                     OffscreenRenderJobCallback callback,
                     void* callback_user_data,
                     OffscreenRenderDiagnosticCallback diagnostics,
                     void* diagnostics_user_data,
                     const OffscreenRenderDemand* demands,
                     size_t demand_count,
                     OffscreenMaterialDependencyCallback materials,
                     void* materials_user_data,
                     const OffscreenRenderCacheOptions* cache,
                     OffscreenRenderCaptureCallbacks captures) {
            topology = &source_topology;
            job_callback = callback;
            job_user_data = callback_user_data;
            diagnostic_callback = diagnostics;
            diagnostic_user_data = diagnostics_user_data;
            had_error = false;
            material_callback = materials;
            material_user_data = materials_user_data;
            cache_options = cache;
            capture_callbacks = captures;
            jobs.clear();
            producers.clear();
            dependency_edges.clear();

            for (size_t scene_index = 0; scene_index < topology->attached_scene_count(); ++scene_index) {
                const tc_scene_handle scene = topology->attached_scene_at(scene_index);
                if (!tc_scene_alive(scene))
                    continue;
                for (size_t pipeline_index = 0; pipeline_index < topology->pipeline_count(scene); ++pipeline_index) {
                    const tc_pipeline_handle pipeline = topology->pipeline_at(scene, pipeline_index);
                    if (!tc_pipeline_handle_valid(pipeline))
                        continue;
                    const uint32_t job = append_job({
                        OffscreenRenderJobKind::ScenePipeline,
                        scene,
                        TC_RENDER_TARGET_HANDLE_INVALID,
                        TC_VIEWPORT_HANDLE_INVALID,
                        pipeline,
                    });
                    if (job == INVALID_JOB_INDEX)
                        return false;
                    const size_t outputs = topology->pipeline_target_count(scene, pipeline);
                    for (size_t output_index = 0; output_index < outputs; ++output_index) {
                        const tc_viewport_handle viewport =
                            topology->pipeline_target_viewport_at(scene, pipeline, output_index);
                        if (tc_viewport_handle_valid(viewport)) {
                            register_producer(tc_viewport_get_render_target(viewport), job);
                        }
                    }
                }
            }

            for (size_t i = 0; i < topology->managed_render_target_count(); ++i) {
                const tc_render_target_handle target = topology->managed_render_target_at(i);
                if (!ensure_render_target_job(target))
                    return false;
            }

            // Host/editor attachments may point to externally owned render
            // targets. They participate in scheduling without being adopted into
            // managed_render_targets (which would incorrectly transfer lifetime).
            for (size_t i = 0; i < topology->viewport_attachment_count(); ++i) {
                const RenderTopology::ViewportAttachment* attachment = topology->viewport_attachment_at(i);
                if (!attachment || !tc_viewport_handle_valid(attachment->viewport))
                    continue;
                if (!ensure_render_target_job(tc_viewport_get_render_target(attachment->viewport))) {
                    return false;
                }
            }

            prepare_job_scratch(jobs.size());

            for (size_t i = 0; i < topology->viewport_attachment_count(); ++i) {
                const RenderTopology::ViewportAttachment* attachment = topology->viewport_attachment_at(i);
                if (!attachment || !tc_viewport_handle_valid(attachment->viewport))
                    continue;
                const tc_render_target_handle target = tc_viewport_get_render_target(attachment->viewport);
                const uint32_t producer = producer_for(target);
                if (producer == INVALID_JOB_INDEX)
                    continue;

                const bool selected_display =
                    !tc_display_handle_valid(only_display) || tc_display_handle_eq(attachment->display, only_display);
                const bool is_root = selected_display && tc_display_alive(attachment->display) &&
                    tc_display_get_enabled(attachment->display) && tc_viewport_get_enabled(attachment->viewport) &&
                    tc_render_target_get_enabled(target);
                auto& job = jobs[producer];
                if (job.kind == OffscreenRenderJobKind::RenderTarget && (is_root || cache_options) &&
                    (!tc_viewport_handle_valid(job.viewport) || (is_root && !roots[producer]))) {
                    // Keep the viewport context for cached producers while their display is hidden.
                    job.viewport = attachment->viewport;
                }
                if (is_root)
                    roots[producer] = 1;
            }

            for (size_t i = 0; i < demand_count; ++i) {
                const OffscreenRenderDemand& demand = demands[i];
                const tc_render_target_handle target = demand.render_target;
                if (!tc_render_target_alive(target) || !tc_render_target_get_enabled(target)) {
                    continue;
                }
                if (tc_viewport_handle_valid(demand.viewport)) {
                    if (!tc_viewport_alive(demand.viewport) || !tc_viewport_get_enabled(demand.viewport) ||
                        !tc_render_target_handle_eq(tc_viewport_get_render_target(demand.viewport), target)) {
                        continue;
                    }
                }
                const uint32_t producer = producer_for(target);
                if (producer == INVALID_JOB_INDEX)
                    continue;
                roots[producer] = 1;
                if (jobs[producer].kind == OffscreenRenderJobKind::RenderTarget &&
                    tc_viewport_handle_valid(demand.viewport)) {
                    jobs[producer].viewport = demand.viewport;
                }
            }

            if (cache_options) {
                select_dirty_jobs();
                for (size_t i = 0; i < demand_count; ++i) {
                    const uint32_t producer = producer_for(demands[i].render_target);
                    if (producer != INVALID_JOB_INDEX && roots[producer])
                        mark_dirty(producer, "explicit output demand");
                }
                for (size_t i = 0; i < dirty_jobs.size(); ++i) {
                    for (const uint32_t consumer : consumers[dirty_jobs[i]])
                        mark_dirty(consumer, "producer invalidation");
                }
                // Hidden consumers stay stale even if their producer refreshes
                // in this frame and is clean by the time they become visible.
                for (const uint32_t job : dirty_jobs) {
                    const auto cached = cached_jobs.find(cache_keys[job]);
                    if (cached != cached_jobs.end())
                        cached->second.invalidated = true;
                }
            }
            for (uint32_t i = 0; i < jobs.size(); ++i) {
                if (roots[i])
                    visit(i);
            }
            return !had_error;
        }
    };

    OffscreenRenderPlanner::OffscreenRenderPlanner()
        : impl_(new(std::nothrow) Impl()) {
        if (!impl_) {
            tc_log(TC_LOG_ERROR, "[RenderingManager] failed to allocate offscreen planner");
        }
    }

    OffscreenRenderPlanner::~OffscreenRenderPlanner() {
        delete impl_;
    }

    bool OffscreenRenderPlanner::execute(const RenderTopology& topology,
                                         tc_display_handle only_display,
                                         OffscreenRenderJobCallback job_callback,
                                         void* job_user_data,
                                         OffscreenRenderDiagnosticCallback diagnostic_callback,
                                         void* diagnostic_user_data,
                                         const OffscreenRenderDemand* demands,
                                         size_t demand_count,
                                         OffscreenMaterialDependencyCallback material_callback,
                                         void* material_user_data,
                                         const OffscreenRenderCacheOptions* cache_options,
                                         OffscreenRenderCaptureCallbacks capture_callbacks) {
        if (!impl_)
            return false;
        try {
            return impl_->execute(topology,
                                  only_display,
                                  job_callback,
                                  job_user_data,
                                  diagnostic_callback,
                                  diagnostic_user_data,
                                  demands,
                                  demand_count,
                                  material_callback,
                                  material_user_data,
                                  cache_options,
                                  capture_callbacks);
        } catch (const std::bad_alloc&) {
            tc_log(TC_LOG_ERROR, "[RenderingManager] offscreen planner scratch allocation failed");
            if (diagnostic_callback) {
                const OffscreenRenderDiagnostic diagnostic{OffscreenRenderDiagnosticKind::AllocationFailure};
                diagnostic_callback(diagnostic_user_data, &diagnostic);
            }
            return false;
        }
    }

    void OffscreenRenderPlanner::invalidate_outputs() {
        if (impl_)
            impl_->cached_jobs.clear();
    }

    uint64_t OffscreenRenderPlanner::output_revision(tc_render_target_handle target) const {
        if (!impl_)
            return 0;
        const uint32_t producer = impl_->producer_for(target);
        if (producer == INVALID_JOB_INDEX || producer >= impl_->cache_keys.size())
            return 0;
        const auto cached = impl_->cached_jobs.find(impl_->cache_keys[producer]);
        return cached == impl_->cached_jobs.end() ? 0 : cached->second.content_revision;
    }

    void update_viewport_rects(const RenderTopology& topology,
                               tc_display_handle only_display,
                               const OffscreenRenderDemand* demands,
                               size_t demand_count) {
        for (size_t i = 0; i < topology.viewport_attachment_count(); ++i) {
            const RenderTopology::ViewportAttachment* attachment = topology.viewport_attachment_at(i);
            if (!attachment)
                continue;
            const tc_display_handle display = attachment->display;
            const bool demanded = viewport_is_demanded(attachment->viewport, demands, demand_count);
            if (!tc_display_alive(display) ||
                (!demanded && tc_display_handle_valid(only_display) && !tc_display_handle_eq(display, only_display)) ||
                (!demanded && !tc_display_get_enabled(display))) {
                continue;
            }
            tc_render_surface* surface = tc_display_get_surface(display);
            if (!surface)
                continue;
            int width = 0;
            int height = 0;
            tc_render_surface_get_size(surface, &width, &height);
            if (width > 0 && height > 0 && tc_viewport_handle_valid(attachment->viewport)) {
                tc_viewport_update_pixel_rect(attachment->viewport, width, height);
            }
        }
    }

    void sync_viewport_render_target_resolutions(const RenderTopology& topology,
                                                 tc_display_handle only_display,
                                                 const OffscreenRenderDemand* demands,
                                                 size_t demand_count) {
        for (size_t i = 0; i < topology.viewport_attachment_count(); ++i) {
            const RenderTopology::ViewportAttachment* attachment = topology.viewport_attachment_at(i);
            if (!attachment)
                continue;
            const tc_display_handle display = attachment->display;
            const bool demanded = viewport_is_demanded(attachment->viewport, demands, demand_count);
            if (!tc_display_alive(display) ||
                (!demanded && tc_display_handle_valid(only_display) && !tc_display_handle_eq(display, only_display)) ||
                (!demanded && !tc_display_get_enabled(display))) {
                continue;
            }
            const tc_viewport_handle viewport = attachment->viewport;
            if (!tc_viewport_handle_valid(viewport) || !tc_viewport_get_enabled(viewport))
                continue;
            const tc_render_target_handle target = tc_viewport_get_render_target(viewport);
            if (!tc_render_target_handle_valid(target) || !tc_render_target_get_enabled(target) ||
                tc_render_target_get_kind(target) != TC_RENDER_TARGET_TEXTURE_2D ||
                !tc_render_target_get_dynamic_resolution(target)) {
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
