// pull_rendering_manager.cpp - Pull-based rendering manager for WPF/Qt style rendering

#include "termin/render/pull_rendering_manager.hpp"
extern "C" {
#include <tcbase/tc_log.h>
}

namespace termin {

// Singleton
PullRenderingManager* PullRenderingManager::s_instance = nullptr;

PullRenderingManager& PullRenderingManager::instance() {
    if (!s_instance) {
        s_instance = new PullRenderingManager();
    }
    return *s_instance;
}

void PullRenderingManager::reset_for_testing() {
    if (s_instance) {
        delete s_instance;
        s_instance = nullptr;
    }
}

PullRenderingManager::PullRenderingManager() = default;

PullRenderingManager::~PullRenderingManager() {
    shutdown();
}

// Configuration
void PullRenderingManager::set_render_engine(RenderEngine* engine) {
    manager()->set_render_engine(engine);
}

RenderEngine* PullRenderingManager::render_engine() {
    return manager()->render_engine();
}

// Display management
void PullRenderingManager::add_display(tc_display* display) {
    manager()->add_display(display);
    tc_log(TC_LOG_INFO, "[PullRenderingManager] Added display: %s",
           display && tc_display_get_name(display) ? tc_display_get_name(display) : "(unnamed)");
}

void PullRenderingManager::remove_display(tc_display* display) {
    manager()->remove_display(display);
    tc_log(TC_LOG_INFO, "[PullRenderingManager] Removed display: %s",
           display && tc_display_get_name(display) ? tc_display_get_name(display) : "(unnamed)");
}

tc_display* PullRenderingManager::get_display_by_name(const std::string& name) const {
    return const_cast<PullRenderingManager*>(this)->manager()->get_display_by_name(name);
}

const std::vector<tc_display*>& PullRenderingManager::displays() const {
    return const_cast<PullRenderingManager*>(this)->manager()->displays();
}

// Pull-rendering: render and present single display
void PullRenderingManager::render_display(tc_display* display) {
    manager()->render_display(display);
}

// Shutdown
void PullRenderingManager::shutdown() {
    if (owned_manager_) {
        owned_manager_->shutdown();
    }
    owned_manager_.reset();
    manager_ = nullptr;
}

RenderingManager* PullRenderingManager::manager() {
    if (manager_) {
        return manager_;
    }
    if (RenderingManager* existing = RenderingManager::instance_or_null()) {
        manager_ = existing;
        return manager_;
    }
    owned_manager_ = std::make_unique<RenderingManager>();
    manager_ = owned_manager_.get();
    return manager_;
}

} // namespace termin
