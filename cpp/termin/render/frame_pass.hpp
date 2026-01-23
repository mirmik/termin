#pragma once

#include <string>
#include <set>
#include <vector>
#include <utility>
#include <functional>
#include <any>
#include <cstring>

extern "C" {
#include "tc_pass.h"
}

namespace termin {

// Forward declaration
class FramePass;

/**
 * Base class for frame passes in the render graph.
 *
 * A frame pass declares which resources it reads and writes.
 * The FrameGraph uses this information to build a dependency graph
 * and execute passes in topological order.
 *
 * Inplace passes read and write the same physical resource under
 * different names (e.g., read "empty", write "color").
 *
 * NOTE: tc_pass is NOT created automatically. It must be set externally:
 * - Python bindings create external tc_pass (calls Python methods)
 * - C# bindings call init_native_tc_pass() (calls C++ methods via vtable)
 */
class FramePass {
public:
    std::string pass_name;
    std::set<std::string> reads;
    std::set<std::string> writes;
    bool enabled = true;

    // Viewport context for resolution/camera
    // Empty string means offscreen (explicit size in ResourceSpec)
    std::string viewport_name;

    // Debug configuration
    std::string debug_internal_symbol;

    // tc_pass handle for C frame graph integration
    // Set externally by bindings layer (Python or C#)
    tc_pass* _tc_pass = nullptr;

    FramePass() = default;

    FramePass(
        std::string name,
        std::set<std::string> reads_set = {},
        std::set<std::string> writes_set = {}
    ) : pass_name(std::move(name)),
        reads(std::move(reads_set)),
        writes(std::move(writes_set)) {
    }

    virtual ~FramePass() {
        // Only free if we own the tc_pass (native pass created by init_native_tc_pass)
        // External tc_pass is owned by Python/bindings layer
        if (_tc_pass && _tc_pass->kind == TC_NATIVE_PASS) {
            if (_tc_pass->pass_name) free(_tc_pass->pass_name);
            if (_tc_pass->viewport_name) free(_tc_pass->viewport_name);
            if (_tc_pass->debug_internal_symbol) free(_tc_pass->debug_internal_symbol);
            free(_tc_pass);
        }
        _tc_pass = nullptr;
    }

    // Initialize native tc_pass for C++ usage (C#, standalone C++)
    // Call this when NOT using Python bindings
    void init_native_tc_pass() {
        if (_tc_pass) return;  // Already initialized
        _tc_pass = static_cast<tc_pass*>(malloc(sizeof(tc_pass)));
        tc_pass_init(_tc_pass, &_cpp_vtable);
        _tc_pass->kind = TC_NATIVE_PASS;
        _tc_pass->wrapper = this;
    }

    // Get tc_pass handle (syncs state first)
    tc_pass* tc_pass_handle() const {
        _sync_tc_pass();
        return _tc_pass;
    }

    /**
     * Returns list of inplace aliases: pairs of (read_name, write_name)
     * where both names refer to the same physical resource.
     *
     * Empty list means the pass is not inplace.
     */
    virtual std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const {
        return {};
    }

    /**
     * Whether this pass is inplace (reads and writes same resource).
     */
    bool is_inplace() const {
        return !get_inplace_aliases().empty();
    }

    /**
     * Returns list of internal debug symbols available for this pass.
     * Used for debugging intermediate render states.
     */
    virtual std::vector<std::string> get_internal_symbols() const {
        return {};
    }

    /**
     * Set active internal debug point.
     */
    void set_debug_internal_point(const std::string& symbol) {
        debug_internal_symbol = symbol;
    }

    /**
     * Clear internal debug point.
     */
    void clear_debug_internal_point() {
        debug_internal_symbol.clear();
    }

    /**
     * Get current internal debug point.
     */
    const std::string& get_debug_internal_point() const {
        return debug_internal_symbol;
    }

    /**
     * Returns set of all resources this pass needs (reads + writes).
     * Subclasses can override if requirements are dynamic.
     */
    virtual std::set<std::string> required_resources() const {
        std::set<std::string> result = reads;
        result.insert(writes.begin(), writes.end());
        return result;
    }

private:
    // Cached strings for tc_pass callbacks (avoid dangling pointers)
    mutable std::vector<std::string> _cached_reads;
    mutable std::vector<std::string> _cached_writes;
    mutable std::vector<std::string> _cached_aliases;
    mutable std::vector<std::string> _cached_symbols;

    // Static vtable for C++ FramePass objects (used by native tc_pass)
    static const tc_pass_vtable _cpp_vtable;

    // Static callbacks for vtable
    static size_t _cb_get_reads(tc_pass* p, const char** out, size_t max);
    static size_t _cb_get_writes(tc_pass* p, const char** out, size_t max);
    static size_t _cb_get_inplace_aliases(tc_pass* p, const char** out, size_t max);
    static size_t _cb_get_internal_symbols(tc_pass* p, const char** out, size_t max);
    static void _cb_destroy(tc_pass* p);

    void _sync_tc_pass() const {
        if (_tc_pass) {
            // Sync pass_name
            if (_tc_pass->pass_name) free(_tc_pass->pass_name);
            _tc_pass->pass_name = pass_name.empty() ? nullptr : strdup(pass_name.c_str());
            _tc_pass->enabled = enabled;
            // Sync viewport_name
            if (_tc_pass->viewport_name) free(_tc_pass->viewport_name);
            _tc_pass->viewport_name = viewport_name.empty() ? nullptr : strdup(viewport_name.c_str());
        }
    }
};

} // namespace termin
