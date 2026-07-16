#pragma once

#include "termin/engine/termin_engine_api.hpp"
#include "render/tc_render_attachment_context.h"

#include <memory>
#include <string>
#include <vector>


namespace termin {

class RenderTopology;

// A scene-scoped view of live render attachments. Copies share a lifetime
// token and become invalid immediately after the lifecycle callback returns.
class TERMIN_ENGINE_API RenderAttachmentContext {
private:
    struct State;
    std::shared_ptr<State> state_;
    bool invalidates_on_destruction_ = false;

    explicit RenderAttachmentContext(RenderTopology& topology, tc_scene_handle scene);
    void invalidate();
    const State& require_active() const;

    friend class RenderTopology;

public:
    RenderAttachmentContext(const RenderAttachmentContext& other);
    RenderAttachmentContext& operator=(const RenderAttachmentContext& other);
    ~RenderAttachmentContext();

    bool valid() const;
    tc_scene_handle scene() const;
    std::vector<tc_render_target_handle> render_targets() const;
    tc_render_target_handle find_render_target(const std::string& name) const;
    tc_render_target_handle find_camera_target(const tc_component* camera) const;
    tc_pipeline_handle get_pipeline(const std::string& name) const;
};

} // namespace termin
