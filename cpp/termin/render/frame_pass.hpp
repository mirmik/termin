#pragma once

#include <string>
#include <set>
#include <vector>
#include <utility>
#include <functional>
#include <any>
#include <cstring>
#include <atomic>

extern "C" {
#include "tc_pass.h"
}

namespace termin {

/**
 * Base class for frame passes in the render graph.
 *
 * Architecture follows CxxComponent pattern:
 * - tc_pass _c is the FIRST member (enables container_of)
 * - Static vtable dispatches to virtual methods
 * - Reference counting for lifetime management
 *
 * Fields like pass_name, enabled, viewport_name are stored ONLY in _c
 * to avoid duplication. Use accessors to get/set them.
 */
class FramePass {
public:
    // FIRST member - enables pointer arithmetic for container_of
    tc_pass _c;

    // C++ only fields (not in tc_pass)
    std::set<std::string> reads;
    std::set<std::string> writes;

private:
    std::atomic<int> _ref_count{0};

    // Cached strings for tc_pass callbacks (avoid dangling pointers)
    mutable std::vector<std::string> _cached_reads;
    mutable std::vector<std::string> _cached_writes;
    mutable std::vector<std::string> _cached_aliases;
    mutable std::vector<std::string> _cached_symbols;

    // Static vtable for C++ FramePass objects
    static const tc_pass_vtable _cpp_vtable;

    // Static callbacks for vtable
    static void _cb_execute(tc_pass* p, tc_execute_context* ctx);
    static size_t _cb_get_reads(tc_pass* p, const char** out, size_t max);
    static size_t _cb_get_writes(tc_pass* p, const char** out, size_t max);
    static size_t _cb_get_inplace_aliases(tc_pass* p, const char** out, size_t max);
    static size_t _cb_get_resource_specs(tc_pass* p, tc_resource_spec* out, size_t max);
    static size_t _cb_get_internal_symbols(tc_pass* p, const char** out, size_t max);
    static void _cb_destroy(tc_pass* p);
    static void _cb_drop(tc_pass* p);
    static void _cb_retain(tc_pass* p);
    static void _cb_release(tc_pass* p);

public:
    FramePass();

    FramePass(
        const std::string& name,
        std::set<std::string> reads_set = {},
        std::set<std::string> writes_set = {}
    );

    virtual ~FramePass();

    // Prevent copying (tc_pass contains pointers)
    FramePass(const FramePass&) = delete;
    FramePass& operator=(const FramePass&) = delete;

    // Get tc_pass pointer
    tc_pass* tc_pass_ptr() { return &_c; }
    const tc_pass* tc_pass_ptr() const { return &_c; }

    // Recover FramePass* from tc_pass* (container_of pattern)
    // Returns nullptr if p is not a native pass (e.g., Python pass)
    static FramePass* from_tc(tc_pass* p) {
        if (!p || p->kind != TC_NATIVE_PASS) return nullptr;
        return reinterpret_cast<FramePass*>(
            reinterpret_cast<char*>(p) - offsetof(FramePass, _c)
        );
    }

    static const FramePass* from_tc(const tc_pass* p) {
        if (!p || p->kind != TC_NATIVE_PASS) return nullptr;
        return reinterpret_cast<const FramePass*>(
            reinterpret_cast<const char*>(p) - offsetof(FramePass, _c)
        );
    }

    // ========================================================================
    // Accessors for fields stored in _c (no duplication)
    // ========================================================================

    // pass_name
    std::string pass_name_get() const {
        return _c.pass_name ? _c.pass_name : "";
    }
    void pass_name_set(const std::string& name) {
        tc_pass_set_name(&_c, name.c_str());
    }

    // enabled
    bool enabled_get() const { return _c.enabled; }
    void enabled_set(bool v) { _c.enabled = v; }

    // viewport_name
    std::string viewport_name_get() const {
        return _c.viewport_name ? _c.viewport_name : "";
    }
    void viewport_name_set(const std::string& name) {
        if (_c.viewport_name) free(_c.viewport_name);
        _c.viewport_name = name.empty() ? nullptr : strdup(name.c_str());
    }

    // debug_internal_symbol
    std::string debug_internal_symbol_get() const {
        return _c.debug_internal_symbol ? _c.debug_internal_symbol : "";
    }
    void debug_internal_symbol_set(const std::string& sym) {
        if (_c.debug_internal_symbol) free(_c.debug_internal_symbol);
        _c.debug_internal_symbol = sym.empty() ? nullptr : strdup(sym.c_str());
    }

    // Compatibility aliases (for existing code)
    std::string get_pass_name() const { return pass_name_get(); }
    void set_pass_name(const std::string& n) { pass_name_set(n); }
    bool get_enabled() const { return enabled_get(); }
    void set_enabled(bool v) { enabled_set(v); }
    std::string get_viewport_name() const { return viewport_name_get(); }
    void set_viewport_name(const std::string& n) { viewport_name_set(n); }
    std::string get_debug_internal_symbol() const { return debug_internal_symbol_get(); }
    void set_debug_internal_symbol(const std::string& s) { debug_internal_symbol_set(s); }

    // ========================================================================
    // Reference counting
    // ========================================================================

    void retain() { ++_ref_count; }
    void release() {
        int prev = _ref_count.fetch_sub(1);
        if (prev <= 1 && !_c.externally_managed) {
            delete this;
        }
    }
    int ref_count() const { return _ref_count.load(); }

    // ========================================================================
    // Virtual methods for subclasses to override
    // ========================================================================

    virtual void execute(tc_execute_context* ctx) {}

    // Dynamic resource computation - override in subclasses
    // Default implementation returns static reads/writes members
    virtual std::set<std::string> compute_reads() const {
        return reads;
    }

    virtual std::set<std::string> compute_writes() const {
        return writes;
    }

    virtual std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const {
        return {};
    }

    virtual std::vector<std::string> get_internal_symbols() const {
        return {};
    }

    virtual void destroy() {}

    // ========================================================================
    // Convenience methods
    // ========================================================================

    bool is_inplace() const {
        return !get_inplace_aliases().empty();
    }

    void set_debug_internal_point(const std::string& symbol) {
        debug_internal_symbol_set(symbol);
    }

    void clear_debug_internal_point() {
        debug_internal_symbol_set("");
    }

    std::string get_debug_internal_point() const {
        return debug_internal_symbol_get();
    }

    std::set<std::string> required_resources() const {
        std::set<std::string> result = reads;
        result.insert(writes.begin(), writes.end());
        return result;
    }

private:
    void _init_tc_pass();
    void _cleanup_tc_pass();
};

// ============================================================================
// Registration macro for FramePass-based classes
// ============================================================================

#define TC_REGISTER_FRAME_PASS(PassClass)                                    \
    static tc_pass* _factory_##PassClass(void* /*userdata*/) {               \
        auto* pass = new PassClass();                                        \
        pass->retain();                                                      \
        return pass->tc_pass_ptr();                                          \
    }                                                                        \
    static struct _reg_##PassClass {                                         \
        _reg_##PassClass() {                                                 \
            tc_pass_registry_register(                                       \
                #PassClass, _factory_##PassClass, nullptr, TC_NATIVE_PASS);  \
        }                                                                    \
    } _reg_instance_##PassClass

} // namespace termin
