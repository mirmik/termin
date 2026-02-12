#pragma once

#include "../entity/component.hpp"
#include "../entity/component_registry.hpp"
#include "../viewport/tc_viewport_handle.hpp"

#include <string>
#include <cstdint>

struct tc_display;
struct tc_viewport_input_manager;

namespace termin {

class CameraComponent;

/// CameraViewportComponent — manages viewport creation for a camera.
///
/// Attach to an entity that has a CameraComponent.
/// On start (editor or play mode), the component:
///   1. Finds the display by name via RenderingManager
///   2. Creates a viewport on that display (or reuses existing one)
///   3. Assigns pipeline, geometry, layer mask and depth
///
/// On destroy, the viewport is removed from the display.
class CameraViewportComponent : public CxxComponent {
public:
    // --- Serializable fields ---

    /// Target display name to attach to (matched via RenderingManager)
    std::string target_display = "Main";

    /// Pipeline name: "(Default)" = first scene pipeline, empty = none, or explicit name
    std::string pipeline_name = "(Default)";

    /// Normalized viewport rect [0..1]
    float rect_x = 0.0f;
    float rect_y = 0.0f;
    float rect_w = 1.0f;
    float rect_h = 1.0f;

    /// Viewport depth (z-order on display)
    int depth = 0;

    /// Layer mask for rendering
    uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL;

    // --- INSPECT_FIELD registrations ---
    INSPECT_FIELD(CameraViewportComponent, target_display, "Display", "string")
    INSPECT_FIELD(CameraViewportComponent, pipeline_name, "Pipeline", "pipeline_selector")
    INSPECT_FIELD(CameraViewportComponent, rect_x, "Rect X", "float", 0.0, 1.0, 0.01)
    INSPECT_FIELD(CameraViewportComponent, rect_y, "Rect Y", "float", 0.0, 1.0, 0.01)
    INSPECT_FIELD(CameraViewportComponent, rect_w, "Rect W", "float", 0.0, 1.0, 0.01)
    INSPECT_FIELD(CameraViewportComponent, rect_h, "Rect H", "float", 0.0, 1.0, 0.01)
    INSPECT_FIELD(CameraViewportComponent, depth, "Depth", "int", -100, 100, 1)

    // layer_mask is registered manually via InspectFieldInfo (needs kind="layer_mask")

    CameraViewportComponent();

    // --- Lifecycle ---
    void on_render_attach() override;
    void on_render_detach() override;
    void on_destroy() override;

    // --- Public API ---

    /// Get the managed viewport (may be invalid)
    TcViewport viewport() const { return viewport_; }

    /// Re-apply settings to the viewport (call after changing fields at runtime)
    void apply_settings();

    /// Migrate viewport to the display specified in target_display field.
    /// Tears down viewport on old display, sets up on new one.
    /// If old display has auto_remove_when_empty and becomes empty, it is removed.
    void apply_display();

    // Button to apply display change (must be after method declaration)
    INSPECT_BUTTON(CameraViewportComponent, apply_display, "Apply Display",
                   &CameraViewportComponent::apply_display)

    /// Same as apply_display() but also sets target_display first.
    void set_target_display(const std::string& new_name);

private:
    TcViewport viewport_;
    tc_display* display_ = nullptr;
    tc_viewport_input_manager* viewport_input_manager_ = nullptr;

    CameraComponent* find_camera() const;
    void setup_viewport();
    void teardown_viewport();
};

REGISTER_COMPONENT(CameraViewportComponent, CxxComponent);

} // namespace termin
