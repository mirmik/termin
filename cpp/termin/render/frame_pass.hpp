#pragma once

#include <string>
#include <set>
#include <vector>
#include <utility>
#include <functional>
#include <any>
#include <cstring>
#include <atomic>
#include <unordered_map>

extern "C" {
#include "render/tc_pass.h"
}

#include "tc_inspect_cpp.hpp"

#include "termin/render/handles.hpp"
#include "termin/render/resource_spec.hpp"

namespace termin {

// Timing information for internal debug symbols
struct InternalSymbolTiming {
    std::string name;
    double cpu_time_ms = 0.0;
    double gpu_time_ms = 0.0;  // -1.0 if not available yet
};

// Forward declarations
class GraphicsBackend;
class Scene;
class Camera;
class Light;
struct ExecuteContext;

// Viewport rectangle in pixels
struct Rect4i {
    int x = 0;
    int y = 0;
    int width = 0;
    int height = 0;
};

// Resource map type: resource name -> framegraph resource
using ResourceMap = std::unordered_map<std::string, FrameGraphResource*>;
using FBOMap = ResourceMap;  // Legacy alias

// Callbacks for frame debugger integration
struct FrameDebuggerCallbacks {
    void* user_data = nullptr;

    void (*blit_from_pass)(
        void* user_data,
        FramebufferHandle* fb,
        GraphicsBackend* graphics,
        int width,
        int height
    ) = nullptr;

    void (*capture_depth)(
        void* user_data,
        FramebufferHandle* fb,
        int width,
        int height,
        float* out_data
    ) = nullptr;

    void (*on_error)(
        void* user_data,
        const char* message
    ) = nullptr;

    bool is_set() const { return blit_from_pass != nullptr; }
};

// Base class for C++ frame passes in the render graph.
//
// Architecture follows CxxComponent pattern:
// - tc_pass _c is the FIRST member (enables container_of)
// - Static vtable dispatches to virtual methods
// - Reference counting for lifetime management
//
// Fields like pass_name, enabled, viewport_name are stored ONLY in _c
// to avoid duplication. Use accessors to get/set them.
class CxxFramePass {
public:
    // FIRST member - enables pointer arithmetic for container_of
    tc_pass _c;

    // Debugger integration
    FrameDebuggerCallbacks debugger_callbacks;

private:
    std::atomic<int> _ref_count{0};

    // Cached strings for tc_pass callbacks (avoid dangling pointers)
    // These store strings from get_inplace_aliases() and get_internal_symbols()
    // which return std::string that must outlive the callback
    mutable std::vector<std::string> _cached_aliases;
    mutable std::vector<std::string> _cached_symbols;

    // Static vtable for C++ CxxFramePass objects
    static const tc_pass_vtable _cpp_vtable;

    // Static callbacks for vtable
    static void _cb_execute(tc_pass* p, void* ctx);
    static size_t _cb_get_reads(tc_pass* p, const char** out, size_t max);
    static size_t _cb_get_writes(tc_pass* p, const char** out, size_t max);
    static size_t _cb_get_inplace_aliases(tc_pass* p, const char** out, size_t max);
    static size_t _cb_get_resource_specs(tc_pass* p, void* out, size_t max);
    static size_t _cb_get_internal_symbols(tc_pass* p, const char** out, size_t max);
    static void _cb_destroy(tc_pass* p);
    static void _cb_drop(tc_pass* p);
    static void _cb_retain(tc_pass* p);
    static void _cb_release(tc_pass* p);

public:
    CxxFramePass();
    virtual ~CxxFramePass();

    // Prevent copying (tc_pass contains pointers)
    CxxFramePass(const CxxFramePass&) = delete;
    CxxFramePass& operator=(const CxxFramePass&) = delete;

    // Get tc_pass pointer
    tc_pass* tc_pass_ptr() { return &_c; }
    const tc_pass* tc_pass_ptr() const { return &_c; }

    // Recover CxxFramePass* from tc_pass* (container_of pattern)
    // Returns nullptr if p is not a native pass (e.g., Python pass)
    static CxxFramePass* from_tc(tc_pass* p) {
        if (!p || p->kind != TC_NATIVE_PASS) return nullptr;
        return reinterpret_cast<CxxFramePass*>(
            reinterpret_cast<char*>(p) - offsetof(CxxFramePass, _c)
        );
    }

    static const CxxFramePass* from_tc(const tc_pass* p) {
        if (!p || p->kind != TC_NATIVE_PASS) return nullptr;
        return reinterpret_cast<const CxxFramePass*>(
            reinterpret_cast<const char*>(p) - offsetof(CxxFramePass, _c)
        );
    }

    // Link to type registry (call after construction if not created via factory)
    void link_to_type_registry(const char* type_name) {
        if (!type_name) return;

        // Ensure type is registered
        if (!tc_pass_registry_has(type_name)) {
            tc_pass_registry_register(type_name, nullptr, nullptr, TC_NATIVE_PASS);
        }

        tc_type_entry* entry = tc_pass_registry_get_entry(type_name);
        if (entry) {
            _c.type_entry = entry;
            _c.type_version = entry->version;
        }
    }

    // Setup external wrapper (for Python/other bindings)
    // Caller is responsible for preventing wrapper from being GC'd
    void set_external_body(void* body) {
        _c.body = body;
        _c.externally_managed = true;
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

    virtual void execute(ExecuteContext& ctx) {}

    // Dynamic resource computation - override in subclasses
    // Returns const char* pointers (use string literals or interned strings)
    virtual std::set<const char*> compute_reads() const { return {}; }
    virtual std::set<const char*> compute_writes() const { return {}; }

    virtual std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const {
        return {};
    }

    virtual std::vector<std::string> get_internal_symbols() const {
        return {};
    }

    virtual std::vector<InternalSymbolTiming> get_internal_symbols_with_timing() const {
        return {};
    }

    // Resource specs - size, clear values, format
    virtual std::vector<ResourceSpec> get_resource_specs() const {
        return {};
    }

    virtual void destroy() {}

    // ========================================================================
    // Debugger integration
    // ========================================================================

    void set_debugger_callbacks(const FrameDebuggerCallbacks& callbacks) {
        debugger_callbacks = callbacks;
    }

    void clear_debugger_callbacks() {
        debugger_callbacks = {};
    }

    bool has_debugger() const {
        return debugger_callbacks.is_set();
    }

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

    std::set<const char*> required_resources() const {
        auto result = compute_reads();
        auto w = compute_writes();
        result.insert(w.begin(), w.end());
        return result;
    }

private:
    void _init_tc_pass();
    void _cleanup_tc_pass();
};

// ============================================================================
// Registration macro for CxxFramePass-based classes
// ============================================================================

#define TC_REGISTER_FRAME_PASS(PassClass)                                    \
    static tc_pass* _factory_##PassClass(void* /*userdata*/) {               \
        auto* pass = new PassClass();                                        \
        pass->retain();                                                      \
        tc_pass* c = pass->tc_pass_ptr();                                    \
        tc_type_entry* entry = tc_pass_registry_get_entry(#PassClass);       \
        if (entry) {                                                         \
            c->type_entry = entry;                                           \
            c->type_version = entry->version;                                \
        }                                                                    \
        return c;                                                            \
    }                                                                        \
    static struct _reg_##PassClass {                                         \
        _reg_##PassClass() {                                                 \
            tc_pass_registry_register(                                       \
                #PassClass, _factory_##PassClass, nullptr, TC_NATIVE_PASS);  \
        }                                                                    \
    } _reg_instance_##PassClass

// Registration macro with parent class for InspectRegistry inheritance
#define TC_REGISTER_FRAME_PASS_DERIVED(PassClass, ParentClass)               \
    static tc_pass* _factory_##PassClass(void* /*userdata*/) {               \
        auto* pass = new PassClass();                                        \
        pass->retain();                                                      \
        tc_pass* c = pass->tc_pass_ptr();                                    \
        tc_type_entry* entry = tc_pass_registry_get_entry(#PassClass);       \
        if (entry) {                                                         \
            c->type_entry = entry;                                           \
            c->type_version = entry->version;                                \
        }                                                                    \
        return c;                                                            \
    }                                                                        \
    static struct _reg_##PassClass {                                         \
        _reg_##PassClass() {                                                 \
            tc_pass_registry_register(                                       \
                #PassClass, _factory_##PassClass, nullptr, TC_NATIVE_PASS);  \
            tc::InspectRegistry::instance().set_type_parent(                 \
                #PassClass, #ParentClass);                                   \
        }                                                                    \
    } _reg_instance_##PassClass

} // namespace termin
