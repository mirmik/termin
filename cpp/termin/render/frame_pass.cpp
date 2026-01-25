// frame_pass.cpp - FramePass implementation with embedded tc_pass
#include "frame_pass.hpp"
#include <algorithm>
#include <cstdlib>

namespace termin {

// ============================================================================
// Static vtable callbacks - use from_tc() to recover C++ object
// ============================================================================

void FramePass::_cb_execute(tc_pass* p, tc_execute_context* ctx) {
    FramePass* self = from_tc(p);
    if (!self || !ctx) return;
    self->execute(ctx);
}

size_t FramePass::_cb_get_reads(tc_pass* p, const char** out, size_t max) {
    FramePass* self = from_tc(p);
    if (!self || !out) return 0;

    // Use virtual compute_reads() for dynamic resource computation
    auto computed_reads = self->compute_reads();
    self->_cached_reads.clear();
    self->_cached_reads.reserve(computed_reads.size());
    for (const auto& r : computed_reads) {
        self->_cached_reads.push_back(r);
    }

    size_t count = std::min(self->_cached_reads.size(), max);
    for (size_t i = 0; i < count; i++) {
        out[i] = self->_cached_reads[i].c_str();
    }
    return count;
}

size_t FramePass::_cb_get_writes(tc_pass* p, const char** out, size_t max) {
    FramePass* self = from_tc(p);
    if (!self || !out) return 0;

    // Use virtual compute_writes() for dynamic resource computation
    auto computed_writes = self->compute_writes();
    self->_cached_writes.clear();
    self->_cached_writes.reserve(computed_writes.size());
    for (const auto& w : computed_writes) {
        self->_cached_writes.push_back(w);
    }

    size_t count = std::min(self->_cached_writes.size(), max);
    for (size_t i = 0; i < count; i++) {
        out[i] = self->_cached_writes[i].c_str();
    }
    return count;
}

size_t FramePass::_cb_get_inplace_aliases(tc_pass* p, const char** out, size_t max) {
    FramePass* self = from_tc(p);
    if (!self || !out) return 0;

    auto aliases = self->get_inplace_aliases();
    self->_cached_aliases.clear();
    self->_cached_aliases.reserve(aliases.size() * 2);

    for (const auto& [read_name, write_name] : aliases) {
        self->_cached_aliases.push_back(read_name);
        self->_cached_aliases.push_back(write_name);
    }

    size_t pair_count = std::min(aliases.size(), max);
    for (size_t i = 0; i < pair_count; i++) {
        out[i * 2] = self->_cached_aliases[i * 2].c_str();
        out[i * 2 + 1] = self->_cached_aliases[i * 2 + 1].c_str();
    }
    return pair_count;
}

size_t FramePass::_cb_get_resource_specs(tc_pass* p, tc_resource_spec* out, size_t max) {
    // Resource specs are handled by RenderFramePass, not base FramePass
    // This callback returns 0 by default
    (void)p;
    (void)out;
    (void)max;
    return 0;
}

size_t FramePass::_cb_get_internal_symbols(tc_pass* p, const char** out, size_t max) {
    FramePass* self = from_tc(p);
    if (!self || !out) return 0;

    self->_cached_symbols = self->get_internal_symbols();

    size_t count = std::min(self->_cached_symbols.size(), max);
    for (size_t i = 0; i < count; i++) {
        out[i] = self->_cached_symbols[i].c_str();
    }
    return count;
}

void FramePass::_cb_destroy(tc_pass* p) {
    FramePass* self = from_tc(p);
    if (self) {
        self->destroy();
    }
}

void FramePass::_cb_drop(tc_pass* p) {
    FramePass* self = from_tc(p);
    if (self && !p->externally_managed) {
        delete self;
    }
}

void FramePass::_cb_retain(tc_pass* p) {
    if (!p) return;
    if (p->externally_managed && p->body) {
        tc_pass_body_incref(p->body);
    } else {
        FramePass* self = from_tc(p);
        if (self) {
            self->retain();
        }
    }
}

void FramePass::_cb_release(tc_pass* p) {
    if (!p) return;
    if (p->externally_managed && p->body) {
        tc_pass_body_decref(p->body);
    } else {
        FramePass* self = from_tc(p);
        if (self) {
            self->release();
        }
    }
}

// ============================================================================
// Static vtable definition
// ============================================================================

const tc_pass_vtable FramePass::_cpp_vtable = {
    .type_name = "CppFramePass",
    .execute = FramePass::_cb_execute,
    .get_reads = FramePass::_cb_get_reads,
    .get_writes = FramePass::_cb_get_writes,
    .get_inplace_aliases = FramePass::_cb_get_inplace_aliases,
    .get_resource_specs = FramePass::_cb_get_resource_specs,
    .get_internal_symbols = FramePass::_cb_get_internal_symbols,
    .destroy = FramePass::_cb_destroy,
    .drop = FramePass::_cb_drop,
    .retain = FramePass::_cb_retain,
    .release = FramePass::_cb_release,
    .serialize = nullptr,
    .deserialize = nullptr,
};

// ============================================================================
// Constructors / Destructor
// ============================================================================

FramePass::FramePass() {
    _init_tc_pass();
}

FramePass::FramePass(
    const std::string& name,
    std::set<std::string> reads_set,
    std::set<std::string> writes_set
) : reads(std::move(reads_set)),
    writes(std::move(writes_set))
{
    _init_tc_pass();
    set_pass_name(name);
}

FramePass::~FramePass() {
    _cleanup_tc_pass();
}

// ============================================================================
// tc_pass management
// ============================================================================

void FramePass::_init_tc_pass() {
    tc_pass_init(&_c, &_cpp_vtable);
    _c.kind = TC_NATIVE_PASS;
}

void FramePass::_cleanup_tc_pass() {
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
