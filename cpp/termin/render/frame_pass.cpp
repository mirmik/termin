// frame_pass.cpp - CxxFramePass implementation with embedded tc_pass
#include "frame_pass.hpp"
#include "execute_context.hpp"
#include "termin/tc_scene_ref.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/lighting/light.hpp"
#include <algorithm>
#include <cstdlib>
#include <cstring>

extern "C" {
#include "termin_core.h"
}

namespace termin {

// ============================================================================
// Static vtable callbacks - use from_tc() to recover C++ object
// ============================================================================

void CxxFramePass::_cb_execute(tc_pass* p, void* ctx) {
    CxxFramePass* self = from_tc(p);
    if (!self || !ctx) return;

    // ctx is ExecuteContext* for C++ passes
    ExecuteContext* cpp_ctx = static_cast<ExecuteContext*>(ctx);
    self->execute(*cpp_ctx);
}

size_t CxxFramePass::_cb_get_reads(tc_pass* p, const char** out, size_t max) {
    CxxFramePass* self = from_tc(p);
    if (!self || !out) return 0;

    auto computed_reads = self->compute_reads();
    size_t count = std::min(computed_reads.size(), max);
    size_t i = 0;
    for (const char* r : computed_reads) {
        if (i >= count) break;
        out[i++] = r;
    }
    return count;
}

size_t CxxFramePass::_cb_get_writes(tc_pass* p, const char** out, size_t max) {
    CxxFramePass* self = from_tc(p);
    if (!self || !out) return 0;

    auto computed_writes = self->compute_writes();
    size_t count = std::min(computed_writes.size(), max);
    size_t i = 0;
    for (const char* w : computed_writes) {
        if (i >= count) break;
        out[i++] = w;
    }
    return count;
}

size_t CxxFramePass::_cb_get_inplace_aliases(tc_pass* p, const char** out, size_t max) {
    CxxFramePass* self = from_tc(p);
    if (!self || !out) return 0;

    auto aliases = self->get_inplace_aliases();
    self->_cached_aliases.clear();
    self->_cached_aliases.reserve(aliases.size() * 2);

    // Store strings in cache to keep them alive
    for (const auto& [read_name, write_name] : aliases) {
        self->_cached_aliases.push_back(read_name);
        self->_cached_aliases.push_back(write_name);
    }

    // Output pointers to cached strings
    size_t pair_count = std::min(aliases.size(), max);
    for (size_t i = 0; i < pair_count; i++) {
        out[i * 2] = self->_cached_aliases[i * 2].c_str();
        out[i * 2 + 1] = self->_cached_aliases[i * 2 + 1].c_str();
    }
    return pair_count;
}

size_t CxxFramePass::_cb_get_resource_specs(tc_pass* p, tc_resource_spec* out, size_t max) {
    CxxFramePass* self = from_tc(p);
    if (!self || !out) return 0;

    auto specs = self->get_resource_specs();
    size_t count = std::min(specs.size(), max);

    for (size_t i = 0; i < count; i++) {
        const auto& spec = specs[i];
        tc_resource_spec& tc_spec = out[i];

        // Resource name - use interned string
        tc_spec.resource = tc_intern_string(spec.resource.c_str());

        // Resource type
        strncpy(tc_spec.resource_type, spec.resource_type.c_str(), sizeof(tc_spec.resource_type) - 1);
        tc_spec.resource_type[sizeof(tc_spec.resource_type) - 1] = '\0';

        // Size
        if (spec.size) {
            tc_spec.fixed_width = spec.size->first;
            tc_spec.fixed_height = spec.size->second;
        } else {
            tc_spec.fixed_width = 0;
            tc_spec.fixed_height = 0;
        }

        // Samples
        tc_spec.samples = spec.samples;

        // Clear color
        if (spec.clear_color) {
            tc_spec.has_clear_color = true;
            tc_spec.clear_color[0] = static_cast<float>(spec.clear_color.value()[0]);
            tc_spec.clear_color[1] = static_cast<float>(spec.clear_color.value()[1]);
            tc_spec.clear_color[2] = static_cast<float>(spec.clear_color.value()[2]);
            tc_spec.clear_color[3] = static_cast<float>(spec.clear_color.value()[3]);
        } else {
            tc_spec.has_clear_color = false;
        }

        // Clear depth
        if (spec.clear_depth) {
            tc_spec.has_clear_depth = true;
            tc_spec.clear_depth = *spec.clear_depth;
        } else {
            tc_spec.has_clear_depth = false;
        }

        // Format
        if (spec.format) {
            tc_spec.format = tc_intern_string(spec.format->c_str());
        } else {
            tc_spec.format = nullptr;
        }
    }

    return count;
}

size_t CxxFramePass::_cb_get_internal_symbols(tc_pass* p, const char** out, size_t max) {
    CxxFramePass* self = from_tc(p);
    if (!self || !out) return 0;

    self->_cached_symbols = self->get_internal_symbols();

    size_t count = std::min(self->_cached_symbols.size(), max);
    for (size_t i = 0; i < count; i++) {
        out[i] = self->_cached_symbols[i].c_str();
    }
    return count;
}

void CxxFramePass::_cb_destroy(tc_pass* p) {
    CxxFramePass* self = from_tc(p);
    if (self) {
        self->destroy();
    }
}

void CxxFramePass::_cb_drop(tc_pass* p) {
    CxxFramePass* self = from_tc(p);
    if (self && !p->externally_managed) {
        delete self;
    }
}

void CxxFramePass::_cb_retain(tc_pass* p) {
    if (!p) return;
    if (p->externally_managed && p->body) {
        tc_pass_body_incref(p->body);
    } else {
        CxxFramePass* self = from_tc(p);
        if (self) {
            self->retain();
        }
    }
}

void CxxFramePass::_cb_release(tc_pass* p) {
    if (!p) return;
    if (p->externally_managed && p->body) {
        tc_pass_body_decref(p->body);
    } else {
        CxxFramePass* self = from_tc(p);
        if (self) {
            self->release();
        }
    }
}

// ============================================================================
// Static vtable definition
// ============================================================================

const tc_pass_vtable CxxFramePass::_cpp_vtable = {
    .execute = CxxFramePass::_cb_execute,
    .get_reads = CxxFramePass::_cb_get_reads,
    .get_writes = CxxFramePass::_cb_get_writes,
    .get_inplace_aliases = CxxFramePass::_cb_get_inplace_aliases,
    .get_resource_specs = CxxFramePass::_cb_get_resource_specs,
    .get_internal_symbols = CxxFramePass::_cb_get_internal_symbols,
    .destroy = CxxFramePass::_cb_destroy,
    .drop = CxxFramePass::_cb_drop,
    .retain = CxxFramePass::_cb_retain,
    .release = CxxFramePass::_cb_release,
    .serialize = nullptr,
    .deserialize = nullptr,
};

// ============================================================================
// Constructors / Destructor
// ============================================================================

CxxFramePass::CxxFramePass() {
    _init_tc_pass();
}

CxxFramePass::~CxxFramePass() {
    _cleanup_tc_pass();
}

// ============================================================================
// tc_pass management
// ============================================================================

void CxxFramePass::_init_tc_pass() {
    tc_pass_init(&_c, &_cpp_vtable);
    _c.kind = TC_NATIVE_PASS;
}

void CxxFramePass::_cleanup_tc_pass() {
    if (_c.pass_name) {
        free(_c.pass_name);
        _c.pass_name = nullptr;
    }
    if (_c.viewport_name) {
        free(_c.viewport_name);
        _c.viewport_name = nullptr;
    }
    if (_c.debug_internal_symbol) {
        free(_c.debug_internal_symbol);
        _c.debug_internal_symbol = nullptr;
    }
}

} // namespace termin
