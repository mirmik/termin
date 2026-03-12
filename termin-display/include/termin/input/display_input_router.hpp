// display_input_router.hpp - C++ RAII wrapper for tc_display_input_router
#pragma once

extern "C" {
#include "render/tc_display_input_router.h"
}

namespace termin {

class DisplayInputRouter {
public:
    tc_display_input_router* router_ = nullptr;

    explicit DisplayInputRouter(tc_display* display) {
        router_ = tc_display_input_router_new(display);
    }

    ~DisplayInputRouter() {
        if (router_) {
            tc_display_input_router_free(router_);
            router_ = nullptr;
        }
    }

    // Non-copyable
    DisplayInputRouter(const DisplayInputRouter&) = delete;
    DisplayInputRouter& operator=(const DisplayInputRouter&) = delete;

    // Movable
    DisplayInputRouter(DisplayInputRouter&& other) noexcept : router_(other.router_) {
        other.router_ = nullptr;
    }
    DisplayInputRouter& operator=(DisplayInputRouter&& other) noexcept {
        if (this != &other) {
            if (router_) tc_display_input_router_free(router_);
            router_ = other.router_;
            other.router_ = nullptr;
        }
        return *this;
    }

    tc_input_manager* input_manager_ptr() {
        return router_ ? tc_display_input_router_base(router_) : nullptr;
    }
};

} // namespace termin
