#include <termin/render/frame_graph_schedule.hpp>

#include <algorithm>
#include <bitset>

#include <tcbase/tc_log.hpp>
#include <termin/render/frame_graph_capture.hpp>
#include <termin/render/render_pipeline.hpp>

namespace termin {
    namespace {
        using PassSet = std::bitset<TC_FRAME_GRAPH_MAX_PASSES>;

        // Compile the attachment graph independently of pass ordering. An
        // in-place write has the same storage as its input but is a distinct
        // logical version for scheduling and capture boundaries.
        bool prepare_attachment_sources(RenderPipeline& pipeline, tc_frame_graph* graph) {
            auto& cache = pipeline.cache();
            const uint64_t revision = tc_pipeline_render_revision(pipeline.handle());
            if (cache.attachment_sources_revision == revision)
                return true;

            struct Node {
                AttachmentSources sources;
                Node* color_input = nullptr;
                Node* depth_input = nullptr;
                std::vector<Node*> users;
                unsigned pending = 0;
            };
            std::unordered_map<std::string, Node> nodes;
            std::unordered_map<std::string, std::string> viewport_slots;
            std::unordered_map<std::string_view, const char*> inplace_inputs;
            const auto add_slot = [&](const char* name) {
                nodes.try_emplace(name);
                viewport_slots[tc_frame_graph_canonical_resource(graph, name)] = name;
            };
            for (const auto& slot : cache.external_texture_slots)
                add_slot(slot.c_str());
            for (const auto& spec : cache.specs) {
                nodes.try_emplace(spec.resource);
                if (spec.resource_type.starts_with("external"))
                    add_slot(spec.resource.c_str());
            }
            for (const char* slot : {"RT_COLOR", "DISPLAY", "OUTPUT", "RT_DEPTH"})
                add_slot(slot);
            for (const auto& output : cache.color_exports)
                nodes.try_emplace(output.resource);
            for (const auto& [name, view] : cache.resource_views) {
                nodes.try_emplace(name);
                nodes.try_emplace(view.parent);
            }
            for (const auto& [name, composition] : cache.fbo_compositions) {
                nodes.try_emplace(name);
                if (!composition.color.empty())
                    nodes.try_emplace(composition.color);
                if (!composition.depth.empty())
                    nodes.try_emplace(composition.depth);
            }
            for (size_t i = 0; i < tc_frame_graph_schedule_count(graph); ++i) {
                const auto pass = tc_frame_graph_resources_at(graph, i);
                for (size_t j = 0; j < pass.read_count; ++j)
                    nodes.try_emplace(pass.reads[j]);
                for (size_t j = 0; j < pass.write_count; ++j)
                    nodes.try_emplace(pass.writes[j]);
                for (size_t j = 0; j < pass.alias_count; ++j) {
                    const char* from = pass.aliases[j * 2];
                    const char* to = pass.aliases[j * 2 + 1];
                    nodes.try_emplace(from);
                    nodes.try_emplace(to);
                    if (std::string_view(from) != to)
                        inplace_inputs.emplace(to, from);
                }
            }

            std::vector<Node*> ready;
            for (auto& [name, node] : nodes) {
                const auto input = [&](const std::string& resource) -> Node* {
                    if (resource.empty())
                        return nullptr;
                    Node& source = nodes.at(resource);
                    source.users.push_back(&node);
                    ++node.pending;
                    return &source;
                };
                const char* canonical = tc_frame_graph_canonical_resource(graph, name.c_str());
                if (auto view = cache.resource_views.find(name); view != cache.resource_views.end()) {
                    if (view->second.attachment == AttachmentKind::Color) {
                        node.color_input = input(view->second.parent);
                    } else {
                        node.depth_input = input(view->second.parent);
                        node.sources.depth_view = true;
                    }
                } else if (auto composition = cache.fbo_compositions.find(name); composition != cache.fbo_compositions.end()) {
                    node.color_input = input(composition->second.color);
                    node.depth_input = input(composition->second.depth);
                } else if (auto alias = inplace_inputs.find(name); alias != inplace_inputs.end() &&
                           !is_external_output_resource(name.c_str())) {
                    // Going straight to the alias group's canonical name can
                    // skip a split and turn a depth view back into an FBO.
                    node.color_input = node.depth_input = input(alias->second);
                } else if (auto slot = viewport_slots.find(canonical); slot != viewport_slots.end()) {
                    const std::string& external = slot->second;
                    const AttachmentSource source{external, is_external_output_resource(external.c_str())
                        ? AttachmentStorage::ViewportOutput : AttachmentStorage::ViewportSlot};
                    if (!is_external_depth_output(external.c_str()))
                        node.sources.color = source;
                    // A named slot can carry a color or a depth texture;
                    // the current viewport supplies its format with the handle.
                    node.sources.depth = source;
                } else {
                    node.sources.color = node.sources.depth = AttachmentSource{name};
                }
                if (!node.pending)
                    ready.push_back(&node);
            }
            for (size_t i = 0; i < ready.size(); ++i) {
                Node& node = *ready[i];
                if (node.color_input)
                    node.sources.color = node.color_input->sources.color;
                if (node.depth_input) {
                    const auto& source = node.depth_input->sources;
                    node.sources.depth = source.depth;
                    if (node.depth_input == node.color_input)
                        node.sources.depth_view = source.depth_view;
                }
                for (Node* user : node.users)
                    if (--user->pending == 0)
                        ready.push_back(user);
            }
            if (ready.size() != nodes.size()) {
                const auto unresolved = std::find_if(nodes.begin(), nodes.end(), [](const auto& p) { return p.second.pending; });
                tc::Log::error("[FrameGraph] cyclic attachment references at '%s'", unresolved->first.c_str());
                return false;
            }
            cache.attachment_sources.clear();
            for (auto& [name, node] : nodes)
                cache.attachment_sources.emplace(name, std::move(node.sources));
            cache.attachment_sources_revision = revision;
            return true;
        }

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
                require_read(name, reason, SIZE_MAX);
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
                        const auto& sources = cache_.attachment_sources.at(resources.writes[i]);
                        if (sources.color.storage == AttachmentStorage::ViewportOutput ||
                            sources.depth.storage == AttachmentStorage::ViewportOutput) {
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
                        result_.capture_writers[i] = capture_writer(request->resource.c_str(), order_positions);
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

            void retain_storage(const char* name) {
                std::vector<const char*> pending;
                while (name) {
                    if (name[0] && result_.resources.insert(name).second) {
                        const auto inputs = backing_inputs(name);
                        if (inputs.first) {
                            if (inputs.second && inputs.second[0] && std::string_view(inputs.first) != inputs.second)
                                pending.push_back(inputs.second);
                            name = inputs.first;
                            continue;
                        }
                        const char* canonical = tc_frame_graph_canonical_resource(graph_, name);
                        if (std::string_view(canonical) != name) {
                            name = canonical;
                            continue;
                        }
                        const auto& sources = cache_.attachment_sources.at(name);
                        // A caller-owned output may be an in-place alias of
                        // this canonical name. Keep the named slot visible to
                        // render-target context construction as well.
                        if (!sources.color.name.empty() && sources.color.name != name)
                            result_.resources.insert(sources.color.name);
                        if (!is_external_output_resource(canonical))
                            result_.canonical_resources.push_back(canonical);
                    }
                    if (pending.empty())
                        return;
                    name = pending.back();
                    pending.pop_back();
                }
            }

            void require_read(const char* name, FrameGraphPassReason reason, size_t consumer) {
                retain_storage(name);
                visit_writers(name, consumer, false, [&](size_t writer) {
                    if (consumer != SIZE_MAX) prerequisites_[consumer].set(writer);
                    select_pass(writer, reason);
                });
            }

            void select_pass(size_t index, FrameGraphPassReason reason) {
                const auto previous = result_.reasons[index];
                result_.reasons[index] = std::max(previous, reason);
                if (previous != FrameGraphPassReason::Unreachable)
                    return;
                const auto resources = tc_frame_graph_resources_at(graph_, index);
                for (size_t i = 0; i < resources.read_count; ++i)
                    require_read(resources.reads[i], FrameGraphPassReason::Dependency, index);
                for (size_t i = 0; i < resources.alias_count; ++i)
                    require_read(resources.aliases[i * 2], FrameGraphPassReason::Dependency, index);
                for (size_t i = 0; i < resources.write_count; ++i)
                    retain_storage(resources.writes[i]);
            }

            template<class Visitor>
            void visit_writers(const char* root, size_t consumer, bool skip_passthrough, Visitor visit) const {
                std::vector<const char*> pending;
                std::unordered_set<std::string_view> visited;
                const char* name = root;
                while (name && name[0]) {
                    const size_t writer = tc_frame_graph_writer_index(graph_, name);
                    ResourceInputs inputs;
                    if (writer != SIZE_MAX && writer != consumer) {
                        const auto* pass = tc_frame_graph_schedule_at(graph_, writer);
                        const bool alias_marker = skip_passthrough &&
                            std::string_view(tc_pass_type_name(pass)) == "GraphAliasPass";
                        if (!skip_passthrough || (!alias_marker && !pass->passthrough)) {
                            visit(writer);
                        } else {
                            // A split/join marker labels attachments. It never
                            // writes pixels, even when old serialized pass data
                            // sets passthrough=false. A join can have two writers.
                            if (alias_marker)
                                inputs = backing_inputs(name);
                            if (!inputs.first) {
                                const auto resources = tc_frame_graph_resources_at(graph_, writer);
                                for (size_t i = 0; i < resources.alias_count; ++i) {
                                    if (std::string_view(name) == resources.aliases[i * 2 + 1]) {
                                        inputs.first = resources.aliases[i * 2];
                                        break;
                                    }
                                }
                            }
                            if (!inputs.first)
                                inputs = backing_inputs(name);
                        }
                    } else {
                        inputs = backing_inputs(name);
                    }
                    // The common direct writer or unproduced leaf needs no
                    // worklist allocation. Deduplicate only derived inputs.
                    if ((inputs.first || inputs.second) && visited.insert(name).second) {
                        if (inputs.second && inputs.second[0] &&
                            (!inputs.first || std::string_view(inputs.first) != inputs.second))
                            pending.push_back(inputs.second);
                        if (inputs.first && inputs.first[0]) {
                            name = inputs.first;
                            continue;
                        }
                    }
                    if (pending.empty())
                        return;
                    name = pending.back();
                    pending.pop_back();
                }
            }

            size_t capture_writer(const char* name,
                                  const std::array<size_t, TC_FRAME_GRAPH_MAX_PASSES>& positions) const {
                size_t latest = SIZE_MAX;
                visit_writers(name, SIZE_MAX, true, [&](size_t writer) {
                    if (latest == SIZE_MAX || positions[writer] > positions[latest]) latest = writer;
                });
                return latest;
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
        if (!prepare_attachment_sources(pipeline, graph)) {
            FrameGraphSchedule invalid;
            invalid.valid = false;
            return invalid;
        }
        ScheduleBuilder builder(graph, pipeline.cache());
        builder.select_outputs();
        for (const auto& resource : required_resources)
            builder.require_resource(resource.c_str(), FrameGraphPassReason::RequiredResource);
        builder.select_captures(pipeline, captures);
        auto result = builder.finish(captures);
        result.pipeline = pipeline.handle();
        result.pipeline_revision = tc_pipeline_render_revision(pipeline.handle());
        return result;
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
