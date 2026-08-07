#include <termin/render/scene_render_services.hpp>
#include <termin/render/ui_widget_pass.hpp>

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <string_view>
#include <unordered_set>
#include <utility>

#include <tcbase/tc_log.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/ui/tc_scene_ui_document_capability.h>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/render_context.hpp>

namespace termin {
    namespace {

        std::string default_ui_font_path() {
            if (const char* configured = std::getenv("TERMIN_UI_FONT"); configured && configured[0] != '\0') {
                return configured;
            }
            if (const char* sdk_root = std::getenv("TERMIN_SDK"); sdk_root && sdk_root[0] != '\0') {
                return (std::filesystem::path(sdk_root) / "share" / "termin" / "fonts" / "DroidSans.ttf").string();
            }
            return {};
        }

        constexpr std::uint64_t kFnvOffset = UINT64_C(14695981039346656037);
        constexpr std::uint64_t kFnvPrime = UINT64_C(1099511628211);

        std::uint64_t hash_bytes(std::uint64_t value, const void* bytes, std::size_t size) {
            const auto* data = static_cast<const unsigned char*>(bytes);
            for (std::size_t index = 0; index < size; ++index) {
                value ^= data[index];
                value *= kFnvPrime;
            }
            return value;
        }

        std::uint64_t hash_string(std::uint64_t value, std::string_view text) {
            return hash_bytes(value, text.data(), text.size());
        }

        std::uint64_t stable_component_identity(const tc_component* component) {
            const tc_entity_handle owner = tc_component_get_owner(component);
            std::uint64_t value = kFnvOffset;
            const std::string_view entity_uuid =
                tc_entity_handle_valid(owner) ? std::string_view(tc_entity_uuid(owner)) : std::string_view{};
            const std::string_view source_id = std::string_view(tc_component_get_source_id(component));
            value = hash_string(value, entity_uuid);
            value = hash_bytes(value, "/", 1);
            value = hash_string(value, source_id);
            if (!entity_uuid.empty() || !source_id.empty()) {
                return value;
            }

            value = hash_bytes(value, &owner.pool.index, sizeof(owner.pool.index));
            value = hash_bytes(value, &owner.pool.generation, sizeof(owner.pool.generation));
            value = hash_bytes(value, &owner.id.index, sizeof(owner.id.index));
            value = hash_bytes(value, &owner.id.generation, sizeof(owner.id.generation));
            const std::size_t component_index =
                tc_entity_handle_valid(owner) ? tc_entity_component_index(owner, component) : SIZE_MAX;
            return hash_bytes(value, &component_index, sizeof(component_index));
        }

        bool layer_is_visible(tc_entity_handle owner, std::uint64_t layer_mask) {
            if (!tc_entity_handle_valid(owner)) {
                return false;
            }
            const std::uint64_t layer = tc_entity_layer(owner);
            return layer < 64u && (layer_mask & (UINT64_C(1) << layer)) != 0u;
        }

        bool synchronize_render_extent(gui_native::UiDocumentSubmission& submission, int width, int height) {
            if (!tc_ui_presentation_metrics_is_valid(&submission.presentation_metrics)) {
                submission.presentation_metrics = tc_ui_presentation_metrics_identity(tc_ui_size{
                    static_cast<float>(width),
                    static_cast<float>(height),
                });
                return true;
            }

            submission.presentation_metrics.physical_extent = tc_ui_size{
                static_cast<float>(width),
                static_cast<float>(height),
            };
            if (tc_ui_presentation_metrics_is_valid(&submission.presentation_metrics)) {
                return true;
            }

            tc::Log::error("[UIWidgetPass] presentation policy is incompatible with render "
                           "extent %dx%d identity=%llu density=%.3f font=%.3f "
                           "safe_insets=[%.3f,%.3f,%.3f,%.3f]",
                           width,
                           height,
                           static_cast<unsigned long long>(submission.stable_identity),
                           submission.presentation_metrics.density_scale,
                           submission.presentation_metrics.font_scale,
                           submission.presentation_metrics.physical_safe_insets.left,
                           submission.presentation_metrics.physical_safe_insets.top,
                           submission.presentation_metrics.physical_safe_insets.right,
                           submission.presentation_metrics.physical_safe_insets.bottom);
            return false;
        }

        struct SubmissionCollector {
            std::uint64_t layer_mask = UINT64_MAX;
            std::unordered_set<const tc_component*> seen;
            std::vector<gui_native::UiDocumentSubmission> submissions;

            void append(tc_component* component) {
                if (!component || !seen.insert(component).second) {
                    return;
                }
                const tc_entity_handle owner = tc_component_get_owner(component);
                if (!layer_is_visible(owner, layer_mask)) {
                    return;
                }
                tc_scene_ui_document_snapshot snapshot{};
                if (!tc_scene_ui_document_snapshot_get(component, &snapshot)) {
                    tc::Log::error("[UIWidgetPass] scene_ui_document capability failed to "
                                   "produce a snapshot for component type='%s' source_id='%s'",
                                   tc_component_get_type_name(component),
                                   tc_component_get_source_id(component));
                    return;
                }
                gui_native::TcDocument document(snapshot.document);
                if (!document.valid()) {
                    tc::Log::error("[UIWidgetPass] scene_ui_document capability returned a stale "
                                   "document for component type='%s' source_id='%s'",
                                   tc_component_get_type_name(component),
                                   tc_component_get_source_id(component));
                    return;
                }
                gui_native::UiDocumentSubmission submission{
                    document,
                    snapshot.priority,
                    stable_component_identity(component),
                };
                if (document.has_presentation_metrics() &&
                    !document.presentation_metrics(submission.presentation_metrics)) {
                    tc::Log::error("[UIWidgetPass] failed to read explicit presentation metrics "
                                   "for component type='%s' source_id='%s'",
                                   tc_component_get_type_name(component),
                                   tc_component_get_source_id(component));
                    return;
                }
                submissions.push_back(submission);
            }
        };

        bool collect_scene_component(tc_component* component, void* user_data) {
            static_cast<SubmissionCollector*>(user_data)->append(component);
            return true;
        }

        void
        collect_internal_hierarchy(tc_entity_handle entity, bool ancestors_enabled, SubmissionCollector& collector) {
            if (!tc_entity_handle_valid(entity)) {
                return;
            }
            const bool hierarchy_enabled = ancestors_enabled && tc_entity_enabled(entity);
            if (hierarchy_enabled) {
                const std::size_t component_count = tc_entity_component_count(entity);
                for (std::size_t index = 0; index < component_count; ++index) {
                    tc_component* component = tc_entity_component_at(entity, index);
                    if (component && tc_component_get_enabled(component) &&
                        tc_component_has_capability(component, tc_scene_ui_document_capability_id())) {
                        collector.append(component);
                    }
                }
            }

            const std::size_t child_count = tc_entity_children_count(entity);
            for (std::size_t index = 0; index < child_count; ++index) {
                collect_internal_hierarchy(tc_entity_child_at(entity, index), hierarchy_enabled, collector);
            }
        }

    } // namespace

    std::vector<gui_native::UiDocumentSubmission> collect_ui_document_submissions(const ExecuteContext& ctx,
                                                                                  bool include_internal_entities) {
        SubmissionCollector collector;
        const SceneRenderServices* services = require_scene_render_services(ctx, "UIWidgetPass");
        if (!services)
            return {};
        collector.layer_mask = services->layer_mask;
        tc_scene_foreach_with_capability(services->scene.handle(),
                                         tc_scene_ui_document_capability_id(),
                                         collect_scene_component,
                                         &collector,
                                         TC_SCENE_FILTER_ENABLED | TC_SCENE_FILTER_ENTITY_ENABLED);
        if (include_internal_entities && tc_entity_handle_valid(services->internal_entities)) {
            collect_internal_hierarchy(services->internal_entities, true, collector);
        }
        std::sort(collector.submissions.begin(), collector.submissions.end(), [](const auto& left, const auto& right) {
            if (left.priority != right.priority) {
                return left.priority < right.priority;
            }
            if (left.stable_identity != right.stable_identity) {
                return left.stable_identity < right.stable_identity;
            }
            const auto left_handle = left.document.handle();
            const auto right_handle = right.document.handle();
            if (left_handle.index != right_handle.index) {
                return left_handle.index < right_handle.index;
            }
            return left_handle.generation < right_handle.generation;
        });
        return collector.submissions;
    }

    UIWidgetPass::UIWidgetPass(const std::string& input, const std::string& output)
        : input_res(input),
          output_res(output),
          painter_(std::make_unique<gui_native::NativeDocumentPainter>()) {
        configure_font();
        pass_name_set("UIWidgets");
        link_to_type_registry("UIWidgetPass");
    }

    void UIWidgetPass::configure_font() {
        const std::string effective_font_path = font_path.empty() ? default_ui_font_path() : font_path;
        if (font_configuration_attempted_ && effective_font_path == configured_font_path_) {
            return;
        }
        font_configuration_attempted_ = true;
        configured_font_path_ = effective_font_path;
        if (effective_font_path.empty()) {
            tc::Log::error("[UIWidgetPass] native UI font is not configured; set "
                           "TERMIN_UI_FONT or TERMIN_SDK");
            return;
        }
        if (!painter_->set_default_font_path(effective_font_path, 14)) {
            tc::Log::error("[UIWidgetPass] failed to configure native UI font '%s'", effective_font_path.c_str());
        }
    }

    UIWidgetPass::~UIWidgetPass() = default;

    std::set<const char*> UIWidgetPass::compute_reads() const {
        return {input_res.c_str()};
    }

    std::set<const char*> UIWidgetPass::compute_writes() const {
        return {output_res.c_str()};
    }

    std::vector<std::pair<std::string, std::string>> UIWidgetPass::get_inplace_aliases() const {
        return {{input_res, output_res}};
    }

    void UIWidgetPass::execute(ExecuteContext& ctx) {
        if (!ctx.ctx2) {
            tc::Log::error("[UIWidgetPass] ctx.ctx2 is null");
            return;
        }
        configure_font();

        auto in_it = ctx.tex2_reads.find(input_res);
        auto out_it = ctx.tex2_writes.find(output_res);
        if (in_it == ctx.tex2_reads.end() || !in_it->second || out_it == ctx.tex2_writes.end() || !out_it->second) {
            tc::Log::error(
                "[UIWidgetPass] missing tgfx2 resources input='%s' output='%s'", input_res.c_str(), output_res.c_str());
            return;
        }

        const tgfx::TextureHandle input = in_it->second;
        const tgfx::TextureHandle output = out_it->second;
        if (input != output) {
            ctx.ctx2->blit(input, output);
        }

        auto submissions = collect_ui_document_submissions(ctx, include_internal_entities);
        if (submissions.empty()) {
            return;
        }

        const auto output_desc = ctx.ctx2->device().texture_desc(output);
        const int width = ctx.render_rect.width > 0 ? ctx.render_rect.width : static_cast<int>(output_desc.width);
        const int height = ctx.render_rect.height > 0 ? ctx.render_rect.height : static_cast<int>(output_desc.height);
        if (width <= 0 || height <= 0) {
            tc::Log::error(
                "[UIWidgetPass] invalid render extent %dx%d for output '%s'", width, height, output_res.c_str());
            return;
        }
        submissions.erase(std::remove_if(submissions.begin(),
                                         submissions.end(),
                                         [width, height](auto& submission) {
                                             return !synchronize_render_extent(submission, width, height);
                                         }),
                          submissions.end());
        if (submissions.empty()) {
            return;
        }

        ctx.ctx2->begin_pass(output, {}, nullptr, 1.0f, false);
        ctx.ctx2->set_viewport(0, 0, width, height);
        try {
            painter_->paint_documents(*ctx.ctx2, width, height, submissions);
        } catch (const std::exception& error) {
            ctx.ctx2->end_pass();
            tc::Log::error(
                "[UIWidgetPass] failed to paint %zu native document(s): %s", submissions.size(), error.what());
            return;
        } catch (...) {
            ctx.ctx2->end_pass();
            tc::Log::error("[UIWidgetPass] failed to paint %zu native document(s) with "
                           "an unknown exception",
                           submissions.size());
            return;
        }
        ctx.ctx2->end_pass();
    }

    void UIWidgetPass::destroy() {
        if (!painter_ || !painter_->is_open()) {
            return;
        }
        try {
            painter_->release_gpu();
        } catch (const std::exception& error) {
            tc::Log::error("[UIWidgetPass] GPU resource release failed: %s", error.what());
        } catch (...) {
            tc::Log::error("[UIWidgetPass] GPU resource release failed with an unknown "
                           "exception");
        }
    }

    void UIWidgetPass::register_type() {
        auto descriptor = FramePassTypeDescriptorBuilder::native<UIWidgetPass>("UIWidgetPass", "termin-render-passes");
        auto& inspect = descriptor.inspect();
        _register_inspect_input_res(inspect);
        _register_inspect_output_res(inspect);
        _register_inspect_font_path(inspect);
        _register_inspect_include_internal_entities(inspect);
        _register_inspect_metadata_graph(inspect);
        (void)descriptor.commit();
    }

} // namespace termin
