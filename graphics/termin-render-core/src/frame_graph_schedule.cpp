#include <termin/render/frame_graph_schedule.hpp>

#include <algorithm>
#include <bitset>

#include <tcbase/tc_log.hpp>
#include <termin/render/frame_graph_capture.hpp>
#include <termin/render/render_pipeline.hpp>

namespace termin {
    namespace {
        using PassSet = std::bitset<TC_FRAME_GRAPH_MAX_PASSES>;
        constexpr unsigned MaxAttachmentDepth = 32;

        struct ResourceInputs {
            const char* first = nullptr;
            const char* second = nullptr;
        };

        class ScheduleBuilder {
        public:
            ScheduleBuilder(tc_frame_graph* graph, const PipelineRenderCache& cache)
                : graph_(graph), cache_(cache), pass_count_(tc_frame_graph_schedule_count(graph)) {}

            void require_resource(const char* name, FrameGraphPassReason reason) {
                if (!tc_frame_graph_has_resource(graph_, name) && !is_external_output_resource(name) &&
                    !cache_.resource_views.contains(name) && !cache_.fbo_compositions.contains(name) &&
                    std::none_of(cache_.specs.begin(), cache_.specs.end(),
                                 [name](const auto& spec) { return spec.resource == name; })) {
                    return;
                }
                require_read(name, reason, SIZE_MAX, 0);
            }

            void select_outputs() {
                for (const auto& output : cache_.color_exports)
                    require_resource(output.resource.c_str(), FrameGraphPassReason::ColorExport);

                for (size_t index = 0; index < pass_count_; ++index) {
                    const auto* pass = tc_frame_graph_schedule_at(graph_, index);
                    if (pass->side_effect && !pass->passthrough)
                        select_pass(index, FrameGraphPassReason::SideEffect);
                    const auto resources = tc_frame_graph_resources_at(graph_, index);
                    for (size_t i = 0; i < resources.write_count; ++i) {
                        if (writes_external_output(resources.writes[i], 0)) {
                            select_pass(index, FrameGraphPassReason::ExternalOutput);
                            break;
                        }
                    }
                }
            }

            void select_captures(RenderPipeline& pipeline, std::span<FrameGraphCaptureRequest* const> captures) {
                result_.capture_writers.resize(captures.size(), SIZE_MAX);
                for (size_t i = 0; i < captures.size(); ++i) {
                    const auto* request = captures[i];
                    if (!request || request->paused || !request->capture)
                        continue;
                    if (request->kind == FrameGraphCaptureRequestKind::Resource) {
                        const char* resource = request->resource.c_str();
                        require_resource(resource, FrameGraphPassReason::Capture);
                    } else {
                        const auto* pass = pipeline.get_pass_at(request->pass_index);
                        for (size_t index = 0; pass && index < pass_count_; ++index) {
                            if (tc_frame_graph_schedule_at(graph_, index) == pass) {
                                select_pass(index, FrameGraphPassReason::Capture);
                                break;
                            }
                        }
                    }
                }
            }

            FrameGraphSchedule finish(std::span<FrameGraphCaptureRequest* const> captures) {
                // In-place writes have ordering edges from other selected readers
                // of their input. Those readers need not be reachable themselves.
                size_t dependents[TC_FRAME_GRAPH_MAX_PASSES];
                PassSet remaining;
                for (size_t i = 0; i < pass_count_; ++i) {
                    if (result_.reasons[i] == FrameGraphPassReason::Unreachable)
                        continue;
                    remaining.set(i);
                    const size_t count = tc_frame_graph_get_dependents(graph_, i, dependents, std::size(dependents));
                    for (size_t j = 0; j < count; ++j)
                        prerequisites_[dependents[j]].set(i);
                }

                while (remaining.any()) {
                    const size_t before = result_.count;
                    for (size_t i = 0; i < pass_count_; ++i) {
                        if (remaining[i] && (prerequisites_[i] & remaining).none()) {
                            result_.order[result_.count++] = i;
                            remaining.reset(i);
                        }
                    }
                    if (result_.count == before) {
                        tc::Log::error("[FrameGraph] dependency cycle through resource views or compositions");
                        result_.valid = false;
                        break;
                    }
                }

                std::array<size_t, TC_FRAME_GRAPH_MAX_PASSES> order_positions{};
                for (size_t i = 0; i < result_.count; ++i)
                    order_positions[result_.order[i]] = i;
                for (size_t i = 0; i < captures.size(); ++i) {
                    const auto* request = captures[i];
                    if (request && request->kind == FrameGraphCaptureRequestKind::Resource &&
                        !request->paused && request->capture) {
                        result_.capture_writers[i] = capture_writer(request->resource.c_str(), order_positions, 0);
                    }
                }
                return std::move(result_);
            }

        private:
            ResourceInputs backing_inputs(const char* name) const {
                if (const auto view = cache_.resource_views.find(name); view != cache_.resource_views.end())
                    return {view->second.parent.c_str(), nullptr};
                if (const auto composition = cache_.fbo_compositions.find(name); composition != cache_.fbo_compositions.end())
                    return {composition->second.color.c_str(), composition->second.depth.c_str()};
                return {};
            }

            bool writes_external_output(const char* name, unsigned depth) const {
                if (!name || !name[0] || depth == MaxAttachmentDepth)
                    return false;
                const char* canonical = tc_frame_graph_canonical_resource(graph_, name);
                if (is_external_output_resource(name) || is_external_output_resource(canonical))
                    return true;
                const auto inputs = backing_inputs(name);
                return writes_external_output(inputs.first, depth + 1) ||
                       writes_external_output(inputs.second, depth + 1);
            }

            void retain_storage(const char* name) {
                if (!name || !name[0] || !result_.resources.insert(name).second)
                    return;
                const auto inputs = backing_inputs(name);
                if (inputs.first) {
                    retain_storage(inputs.first);
                    retain_storage(inputs.second);
                    return;
                }
                const char* canonical = tc_frame_graph_canonical_resource(graph_, name);
                if (std::string_view(canonical) != name) {
                    retain_storage(canonical);
                } else if (!is_external_output_resource(canonical)) {
                    result_.canonical_resources.push_back(canonical);
                }
            }

            void require_read(const char* name, FrameGraphPassReason reason, size_t consumer, unsigned depth) {
                if (!name || !name[0])
                    return;
                if (depth == MaxAttachmentDepth) {
                    if (result_.valid)
                        tc::Log::error("[FrameGraph] excessive resource view or composition nesting at '%s'", name);
                    result_.valid = false;
                    return;
                }
                retain_storage(name);
                const size_t writer = tc_frame_graph_writer_index(graph_, name);
                if (writer != SIZE_MAX && writer != consumer) {
                    if (consumer != SIZE_MAX)
                        prerequisites_[consumer].set(writer);
                    select_pass(writer, reason);
                    return;
                }
                const auto inputs = backing_inputs(name);
                require_read(inputs.first, reason, consumer, depth + 1);
                if (inputs.second && std::string_view(inputs.second) != inputs.first)
                    require_read(inputs.second, reason, consumer, depth + 1);
            }

            void select_pass(size_t index, FrameGraphPassReason reason) {
                const auto previous = result_.reasons[index];
                result_.reasons[index] = std::max(previous, reason);
                if (previous != FrameGraphPassReason::Unreachable)
                    return;
                const auto resources = tc_frame_graph_resources_at(graph_, index);
                for (size_t i = 0; i < resources.read_count; ++i)
                    require_read(resources.reads[i], FrameGraphPassReason::Dependency, index, 0);
                for (size_t i = 0; i < resources.alias_count; ++i)
                    require_read(resources.aliases[i * 2], FrameGraphPassReason::Dependency, index, 0);
                for (size_t i = 0; i < resources.write_count; ++i)
                    retain_storage(resources.writes[i]);
            }

            size_t capture_writer(const char* name,
                                  const std::array<size_t, TC_FRAME_GRAPH_MAX_PASSES>& positions,
                                  unsigned depth) const {
                if (!name || !name[0] || depth == MaxAttachmentDepth)
                    return SIZE_MAX;
                const size_t writer = tc_frame_graph_writer_index(graph_, name);
                if (writer != SIZE_MAX) {
                    if (!tc_frame_graph_schedule_at(graph_, writer)->passthrough)
                        return writer;
                    const auto resources = tc_frame_graph_resources_at(graph_, writer);
                    for (size_t i = 0; i < resources.alias_count; ++i) {
                        if (std::string_view(name) == resources.aliases[i * 2 + 1])
                            return capture_writer(resources.aliases[i * 2], positions, depth + 1);
                    }
                }
                const auto inputs = backing_inputs(name);
                const size_t first = capture_writer(inputs.first, positions, depth + 1);
                const size_t second = capture_writer(inputs.second, positions, depth + 1);
                if (first == SIZE_MAX || (second != SIZE_MAX && positions[second] > positions[first]))
                    return second;
                return first;
            }

            tc_frame_graph* graph_;
            const PipelineRenderCache& cache_;
            size_t pass_count_;
            FrameGraphSchedule result_;
            std::array<PassSet, TC_FRAME_GRAPH_MAX_PASSES> prerequisites_;
        };
    }

    FrameGraphSchedule select_frame_graph_schedule(RenderPipeline& pipeline,
                                                  tc_frame_graph* graph,
                                                  std::span<FrameGraphCaptureRequest* const> captures,
                                                  std::span<const std::string> required_resources) {
        ScheduleBuilder builder(graph, pipeline.cache());
        builder.select_outputs();
        for (const auto& resource : required_resources)
            builder.require_resource(resource.c_str(), FrameGraphPassReason::RequiredResource);
        builder.select_captures(pipeline, captures);
        return builder.finish(captures);
    }

    const char* frame_graph_pass_reason_name(FrameGraphPassReason reason) {
        switch (reason) {
        case FrameGraphPassReason::Dependency: return "dependency";
        case FrameGraphPassReason::Capture: return "capture";
        case FrameGraphPassReason::RequiredResource: return "required resource";
        case FrameGraphPassReason::ColorExport: return "color export";
        case FrameGraphPassReason::ExternalOutput: return "external output";
        case FrameGraphPassReason::SideEffect: return "side effect";
        case FrameGraphPassReason::Unreachable: return "unused output";
        }
        return "unknown";
    }
}
