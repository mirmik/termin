#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <vector>

#include <termin/gui_native/tc_document.hpp>
#include <tgfx2/handles.hpp>

namespace tgfx {
class IRenderDevice;
class RenderContext2;
}

namespace termin {

class FrameGraphDebugger;

namespace gui_native {
class BoxLayout;
class Button;
class Canvas;
class Checkbox;
class ComboBox;
class RichTextModel;
class StatusBar;
class TextArea;
}

// Editor-specific C++ projection of FrameGraphDebugger into an existing
// tc_ui_document. The view never owns or destroys the document; the
// application composition root keeps that lifecycle explicit.
class FrameGraphDebuggerView {
public:
    FrameGraphDebuggerView(
        gui_native::TcDocument document,
        FrameGraphDebugger& debugger,
        std::function<void()> request_render = {});
    ~FrameGraphDebuggerView();

    FrameGraphDebuggerView(const FrameGraphDebuggerView&) = delete;
    FrameGraphDebuggerView& operator=(const FrameGraphDebuggerView&) = delete;

    bool activate();
    void deactivate();
    bool update();
    bool show_resource(const std::string& resource);
    bool render_previews(tgfx::RenderContext2& context);
    std::string refresh_depth(tgfx::IRenderDevice& device);
    void close();

    bool active() const { return active_; }
    bool closed() const { return closed_; }
    gui_native::TcDocument document() const { return document_; }
    tc_widget_handle root_handle() const;
    const std::vector<size_t>& pass_indices() const { return pass_indices_; }

    gui_native::Widget* root_widget() const;
    gui_native::ComboBox* target_combo() const { return target_combo_; }
    gui_native::ComboBox* mode_combo() const { return mode_combo_; }
    gui_native::ComboBox* pass_combo() const { return pass_combo_; }
    gui_native::ComboBox* symbol_combo() const { return symbol_combo_; }
    gui_native::ComboBox* resource_combo() const { return resource_combo_; }
    gui_native::BoxLayout* inside_panel() const { return inside_panel_; }
    gui_native::BoxLayout* between_panel() const { return between_panel_; }
    gui_native::StatusBar* state_status() const { return state_status_; }

private:
    struct Preview {
        gui_native::Canvas* canvas = nullptr;
        gui_native::StatusBar* status = nullptr;
        tgfx::TextureHandle target{};
        uint32_t width = 0;
        uint32_t height = 0;
        bool force_depth = false;
        bool ready = false;
        bool has_cursor = false;
        int cursor_x = 0;
        int cursor_y = 0;
    };

    void build();
    void select_initial_values();
    void refresh_lists();
    void refresh_selection();
    void refresh_info();
    void refresh_preview_status(Preview& preview);
    bool render_preview(tgfx::RenderContext2& context, Preview& preview);
    void release_previews();
    void release_preview(Preview& preview);
    void request_render();
    void require_open() const;

    gui_native::TcDocument document_;
    FrameGraphDebugger* debugger_ = nullptr;
    std::function<void()> request_render_;
    tgfx::IRenderDevice* preview_device_ = nullptr;

    gui_native::BoxLayout* root_ = nullptr;
    gui_native::ComboBox* target_combo_ = nullptr;
    gui_native::ComboBox* mode_combo_ = nullptr;
    gui_native::ComboBox* pass_combo_ = nullptr;
    gui_native::ComboBox* symbol_combo_ = nullptr;
    gui_native::ComboBox* resource_combo_ = nullptr;
    gui_native::ComboBox* channel_combo_ = nullptr;
    gui_native::Checkbox* pause_check_ = nullptr;
    gui_native::Checkbox* hdr_check_ = nullptr;
    gui_native::BoxLayout* inside_panel_ = nullptr;
    gui_native::BoxLayout* between_panel_ = nullptr;
    gui_native::TextArea* pass_json_ = nullptr;
    std::shared_ptr<gui_native::RichTextModel> pipeline_model_;
    std::shared_ptr<gui_native::RichTextModel> fbo_model_;
    std::shared_ptr<gui_native::RichTextModel> hdr_model_;
    gui_native::StatusBar* state_status_ = nullptr;
    gui_native::StatusBar* stats_bar_ = nullptr;
    gui_native::StatusBar* timing_bar_ = nullptr;
    gui_native::StatusBar* depth_read_status_ = nullptr;
    Preview main_preview_;
    Preview depth_preview_;
    std::vector<size_t> pass_indices_;
    bool updating_ = false;
    bool active_ = false;
    bool closed_ = false;
};

} // namespace termin
