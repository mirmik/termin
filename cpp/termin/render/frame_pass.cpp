// frame_pass.cpp - FramePass tc_pass vtable implementation
#include "frame_pass.hpp"
#include <algorithm>

namespace termin {

// Static vtable for C++ FramePass objects
const tc_pass_vtable FramePass::_cpp_vtable = {
    .type_name = "CppFramePass",
    .execute = nullptr,  // Execute is handled by Python/RenderEngine
    .get_reads = FramePass::_cb_get_reads,
    .get_writes = FramePass::_cb_get_writes,
    .get_inplace_aliases = FramePass::_cb_get_inplace_aliases,
    .get_resource_specs = nullptr,  // Handled separately
    .get_internal_symbols = FramePass::_cb_get_internal_symbols,
    .destroy = FramePass::_cb_destroy,
    .drop = nullptr,
    .retain = nullptr,
    .release = nullptr,
    .serialize = nullptr,
    .deserialize = nullptr,
};

size_t FramePass::_cb_get_reads(tc_pass* p, const char** out, size_t max) {
    if (!p || !p->wrapper || !out) return 0;
    FramePass* self = static_cast<FramePass*>(p->wrapper);

    // Cache strings to avoid dangling pointers
    self->_cached_reads.clear();
    self->_cached_reads.reserve(self->reads.size());
    for (const auto& r : self->reads) {
        self->_cached_reads.push_back(r);
    }

    size_t count = std::min(self->_cached_reads.size(), max);
    for (size_t i = 0; i < count; i++) {
        out[i] = self->_cached_reads[i].c_str();
    }
    return count;
}

size_t FramePass::_cb_get_writes(tc_pass* p, const char** out, size_t max) {
    if (!p || !p->wrapper || !out) return 0;
    FramePass* self = static_cast<FramePass*>(p->wrapper);

    self->_cached_writes.clear();
    self->_cached_writes.reserve(self->writes.size());
    for (const auto& w : self->writes) {
        self->_cached_writes.push_back(w);
    }

    size_t count = std::min(self->_cached_writes.size(), max);
    for (size_t i = 0; i < count; i++) {
        out[i] = self->_cached_writes[i].c_str();
    }
    return count;
}

size_t FramePass::_cb_get_inplace_aliases(tc_pass* p, const char** out, size_t max) {
    if (!p || !p->wrapper || !out) return 0;
    FramePass* self = static_cast<FramePass*>(p->wrapper);

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

size_t FramePass::_cb_get_internal_symbols(tc_pass* p, const char** out, size_t max) {
    if (!p || !p->wrapper || !out) return 0;
    FramePass* self = static_cast<FramePass*>(p->wrapper);

    self->_cached_symbols = self->get_internal_symbols();

    size_t count = std::min(self->_cached_symbols.size(), max);
    for (size_t i = 0; i < count; i++) {
        out[i] = self->_cached_symbols[i].c_str();
    }
    return count;
}

void FramePass::_cb_destroy(tc_pass* p) {
    // Don't delete the C++ object - it's managed by Python/nanobind
    // Just clear the wrapper to prevent double-free
    if (p) {
        p->wrapper = nullptr;
    }
}

} // namespace termin
