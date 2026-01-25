// cxx_pass.cpp - CxxPass implementation
#include "cxx_pass.hpp"
#include "termin/camera/camera_component.hpp"
#include <cstring>
#include <algorithm>

namespace termin {

// ============================================================================
// CxxPass Static Vtable
// ============================================================================

const tc_pass_vtable CxxPass::_cxx_vtable = {
    .execute = CxxPass::_cb_execute,
    .get_reads = CxxPass::_cb_get_reads,
    .get_writes = CxxPass::_cb_get_writes,
    .get_inplace_aliases = CxxPass::_cb_get_inplace_aliases,
    .get_resource_specs = CxxPass::_cb_get_resource_specs,
    .get_internal_symbols = CxxPass::_cb_get_internal_symbols,
    .destroy = CxxPass::_cb_destroy,
    .drop = CxxPass::_cb_drop,
    .retain = nullptr,
    .release = nullptr,
    .serialize = nullptr,
    .deserialize = nullptr,
};

// ============================================================================
// CxxPass Constructor / Destructor
// ============================================================================

CxxPass::CxxPass() {
    tc_pass_init(&_c, &_cxx_vtable);
    _c.kind = TC_NATIVE_PASS;
}

CxxPass::~CxxPass() {
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

// ============================================================================
// CxxPass Accessors
// ============================================================================

void CxxPass::set_pass_name(const std::string& name) {
    if (_c.pass_name) {
        free(_c.pass_name);
    }
    _c.pass_name = name.empty() ? nullptr : strdup(name.c_str());
}

void CxxPass::set_viewport_name(const std::string& name) {
    if (_c.viewport_name) {
        free(_c.viewport_name);
    }
    _c.viewport_name = name.empty() ? nullptr : strdup(name.c_str());
}

void CxxPass::set_debug_internal_symbol(const std::string& symbol) {
    if (_c.debug_internal_symbol) {
        free(_c.debug_internal_symbol);
    }
    _c.debug_internal_symbol = symbol.empty() ? nullptr : strdup(symbol.c_str());
}

void CxxPass::clear_debug_internal_symbol() {
    if (_c.debug_internal_symbol) {
        free(_c.debug_internal_symbol);
        _c.debug_internal_symbol = nullptr;
    }
}

// ============================================================================
// Static Callbacks (dispatch to virtual methods)
// ============================================================================

void CxxPass::_cb_execute(tc_pass* p, tc_execute_context* ctx) {
    CxxPass* self = from_tc(p);
    if (self && ctx) {
        // Convert C context to C++ context
        ExecuteContext cxx_ctx;
        cxx_ctx.graphics = static_cast<GraphicsBackend*>(ctx->graphics);
        cxx_ctx.rect.x = ctx->rect_x;
        cxx_ctx.rect.y = ctx->rect_y;
        cxx_ctx.rect.width = ctx->rect_width;
        cxx_ctx.rect.height = ctx->rect_height;
        cxx_ctx.layer_mask = ctx->layer_mask;
        if (ctx->scene) {
            cxx_ctx.scene = TcSceneRef(static_cast<tc_scene*>(ctx->scene));
        }
        cxx_ctx.camera = static_cast<CameraComponent*>(ctx->camera);
        // reads_fbos/writes_fbos: C passes void* pointers to maps
        if (ctx->reads_fbos) {
            cxx_ctx.reads_fbos = *static_cast<FBOMap*>(ctx->reads_fbos);
        }
        if (ctx->writes_fbos) {
            cxx_ctx.writes_fbos = *static_cast<FBOMap*>(ctx->writes_fbos);
        }
        // lights: C passes void* to vector
        if (ctx->lights && ctx->light_count > 0) {
            auto* lights_vec = static_cast<std::vector<Light>*>(ctx->lights);
            cxx_ctx.lights = *lights_vec;
        }
        self->execute(cxx_ctx);
    }
}

size_t CxxPass::_cb_get_reads(tc_pass* p, const char** out, size_t max) {
    CxxPass* self = from_tc(p);
    if (!self || !out) return 0;

    // Compute reads and cache strings
    auto reads = self->compute_reads();
    self->_cached_reads.clear();
    self->_cached_reads.reserve(reads.size());

    for (const auto& r : reads) {
        self->_cached_reads.push_back(r);
    }

    size_t count = std::min(self->_cached_reads.size(), max);
    for (size_t i = 0; i < count; i++) {
        out[i] = self->_cached_reads[i].c_str();
    }
    return count;
}

size_t CxxPass::_cb_get_writes(tc_pass* p, const char** out, size_t max) {
    CxxPass* self = from_tc(p);
    if (!self || !out) return 0;

    auto writes = self->compute_writes();
    self->_cached_writes.clear();
    self->_cached_writes.reserve(writes.size());

    for (const auto& w : writes) {
        self->_cached_writes.push_back(w);
    }

    size_t count = std::min(self->_cached_writes.size(), max);
    for (size_t i = 0; i < count; i++) {
        out[i] = self->_cached_writes[i].c_str();
    }
    return count;
}

size_t CxxPass::_cb_get_inplace_aliases(tc_pass* p, const char** out, size_t max) {
    CxxPass* self = from_tc(p);
    if (!self || !out) return 0;

    auto aliases = self->get_inplace_aliases();
    self->_cached_aliases.clear();
    self->_cached_aliases.reserve(aliases.size() * 2);

    // Store pairs: read0, write0, read1, write1, ...
    for (const auto& alias : aliases) {
        self->_cached_aliases.push_back(alias.read_name);
        self->_cached_aliases.push_back(alias.write_name);
    }

    size_t pair_count = std::min(aliases.size(), max);
    for (size_t i = 0; i < pair_count; i++) {
        out[i * 2] = self->_cached_aliases[i * 2].c_str();
        out[i * 2 + 1] = self->_cached_aliases[i * 2 + 1].c_str();
    }
    return pair_count;
}

size_t CxxPass::_cb_get_resource_specs(tc_pass* p, tc_resource_spec* out, size_t max) {
    CxxPass* self = from_tc(p);
    if (!self || !out) return 0;

    self->_cached_specs = self->get_resource_specs();

    size_t count = std::min(self->_cached_specs.size(), max);
    for (size_t i = 0; i < count; i++) {
        const auto& spec = self->_cached_specs[i];
        tc_resource_spec& c = out[i];
        memset(&c, 0, sizeof(c));
        c.resource = spec.resource.c_str();
        strncpy(c.resource_type, spec.resource_type.c_str(), sizeof(c.resource_type) - 1);
        if (spec.size) {
            c.fixed_width = spec.size->first;
            c.fixed_height = spec.size->second;
        }
        c.samples = spec.samples;
        if (spec.clear_color) {
            c.has_clear_color = true;
            c.clear_color[0] = static_cast<float>((*spec.clear_color)[0]);
            c.clear_color[1] = static_cast<float>((*spec.clear_color)[1]);
            c.clear_color[2] = static_cast<float>((*spec.clear_color)[2]);
            c.clear_color[3] = static_cast<float>((*spec.clear_color)[3]);
        }
        if (spec.clear_depth) {
            c.has_clear_depth = true;
            c.clear_depth = *spec.clear_depth;
        }
        c.format = spec.format ? spec.format->c_str() : nullptr;
    }
    return count;
}

size_t CxxPass::_cb_get_internal_symbols(tc_pass* p, const char** out, size_t max) {
    CxxPass* self = from_tc(p);
    if (!self || !out) return 0;

    self->_cached_symbols = self->get_internal_symbols();

    size_t count = std::min(self->_cached_symbols.size(), max);
    for (size_t i = 0; i < count; i++) {
        out[i] = self->_cached_symbols[i].c_str();
    }
    return count;
}

void CxxPass::_cb_destroy(tc_pass* p) {
    CxxPass* self = from_tc(p);
    if (self) {
        self->destroy();
    }
}

void CxxPass::_cb_drop(tc_pass* p) {
    CxxPass* self = from_tc(p);
    if (self) {
        delete self;
    }
}

} // namespace termin
