#pragma once

// CxxPass - Base class for C++ render passes
// Same pattern as CxxComponent: embedded tc_pass with virtual dispatch

#include <string>
#include <set>
#include <vector>
#include <cstddef>
#include <unordered_map>

extern "C" {
#include "tc_pass.h"
}

namespace termin {

// Forward declarations
class GraphicsBackend;
class FramebufferHandle;

// ============================================================================
// ExecuteContext - C++ wrapper for tc_execute_context
// ============================================================================

struct ExecuteContext {
    GraphicsBackend* graphics = nullptr;
    std::unordered_map<std::string, FramebufferHandle*>* reads_fbos = nullptr;
    std::unordered_map<std::string, FramebufferHandle*>* writes_fbos = nullptr;
    int rect_x = 0;
    int rect_y = 0;
    int rect_width = 0;
    int rect_height = 0;
    void* scene = nullptr;       // tc_scene*
    void* camera = nullptr;      // Camera*
    int64_t context_key = 0;
    void* lights = nullptr;      // std::vector<Light>*
    size_t light_count = 0;
    uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL;

    // Convenience accessors
    int width() const { return rect_width; }
    int height() const { return rect_height; }

    // Convert from C struct
    static ExecuteContext from_c(tc_execute_context* ctx);

    // Convert to C struct
    tc_execute_context to_c() const;
};

// ============================================================================
// ResourceSpec - C++ wrapper for tc_resource_spec
// ============================================================================

struct ResourceSpec {
    std::string resource;
    int fixed_width = 0;         // 0 = viewport size
    int fixed_height = 0;
    float clear_color[4] = {0, 0, 0, 1};
    float clear_depth = 1.0f;
    bool has_clear_color = false;
    bool has_clear_depth = false;
    std::string format;

    ResourceSpec() = default;

    ResourceSpec(const std::string& res)
        : resource(res) {}

    ResourceSpec(const std::string& res, float r, float g, float b, float a)
        : resource(res), has_clear_color(true) {
        clear_color[0] = r;
        clear_color[1] = g;
        clear_color[2] = b;
        clear_color[3] = a;
    }

    // Convert to C struct
    tc_resource_spec to_c() const;
};

// ============================================================================
// InplaceAlias - pair of read/write names for inplace operations
// ============================================================================

struct InplaceAlias {
    std::string read_name;
    std::string write_name;

    InplaceAlias(const std::string& r, const std::string& w)
        : read_name(r), write_name(w) {}
};

// ============================================================================
// CxxPass - Base class for all C++ render passes
// ============================================================================

class CxxPass {
public:
    // Embedded C pass (MUST be first member for from_tc to work)
    tc_pass _c;

private:
    // Single vtable shared by all C++ passes - dispatches to virtual methods
    static const tc_pass_vtable _cxx_vtable;

public:
    virtual ~CxxPass();

    // Get CxxPass* from tc_pass* (uses offsetof since _c is first member)
    static CxxPass* from_tc(tc_pass* p) {
        if (!p) return nullptr;
        return reinterpret_cast<CxxPass*>(
            reinterpret_cast<char*>(p) - offsetof(CxxPass, _c)
        );
    }

    // Access to underlying C pass
    tc_pass* c_pass() { return &_c; }
    const tc_pass* c_pass() const { return &_c; }

    // ========== Accessors ==========

    const char* pass_name() const { return _c.pass_name; }
    void set_pass_name(const std::string& name);

    bool enabled() const { return _c.enabled; }
    void set_enabled(bool v) { _c.enabled = v; }

    bool passthrough() const { return _c.passthrough; }
    void set_passthrough(bool v) { _c.passthrough = v; }

    const char* viewport_name() const { return _c.viewport_name; }
    void set_viewport_name(const std::string& name);

    const char* debug_internal_symbol() const { return _c.debug_internal_symbol; }
    void set_debug_internal_symbol(const std::string& symbol);
    void clear_debug_internal_symbol();

    // ========== Virtual methods - subclasses override ==========

    // Core execution - MUST be implemented
    virtual void execute(ExecuteContext& ctx) = 0;

    // Resource declarations (dynamic)
    virtual std::set<std::string> compute_reads() { return {}; }
    virtual std::set<std::string> compute_writes() { return {}; }

    // Inplace aliases - resources that share same physical FBO
    virtual std::vector<InplaceAlias> get_inplace_aliases() { return {}; }

    bool is_inplace() const {
        return !const_cast<CxxPass*>(this)->get_inplace_aliases().empty();
    }

    // Resource specs - size, clear values, format
    virtual std::vector<ResourceSpec> get_resource_specs() { return {}; }

    // Debug symbols (entity names for step-through debugging)
    virtual std::vector<std::string> get_internal_symbols() { return {}; }

    // Cleanup (called before pipeline is destroyed)
    virtual void destroy() {}

    // Type name for serialization
    virtual const char* type_name() const { return "CxxPass"; }

protected:
    CxxPass();

private:
    // Static callbacks that dispatch to C++ virtual methods
    static void _cb_execute(tc_pass* p, tc_execute_context* ctx);
    static size_t _cb_get_reads(tc_pass* p, const char** out, size_t max);
    static size_t _cb_get_writes(tc_pass* p, const char** out, size_t max);
    static size_t _cb_get_inplace_aliases(tc_pass* p, const char** out, size_t max);
    static size_t _cb_get_resource_specs(tc_pass* p, tc_resource_spec* out, size_t max);
    static size_t _cb_get_internal_symbols(tc_pass* p, const char** out, size_t max);
    static void _cb_destroy(tc_pass* p);
    static void _cb_drop(tc_pass* p);

    // Cached strings for C API (avoid dangling pointers from std::string)
    mutable std::vector<std::string> _cached_reads;
    mutable std::vector<std::string> _cached_writes;
    mutable std::vector<std::string> _cached_aliases;
    mutable std::vector<std::string> _cached_symbols;
    mutable std::vector<ResourceSpec> _cached_specs;
};

// ============================================================================
// Registration Helper Macro
// ============================================================================

#define TC_REGISTER_PASS(PassClass)                                         \
    static tc_pass* _factory_##PassClass() {                                \
        auto* p = new PassClass();                                          \
        return p->c_pass();                                                 \
    }                                                                       \
    static struct _reg_##PassClass {                                        \
        _reg_##PassClass() {                                                \
            tc_pass_registry_register(                                      \
                #PassClass, _factory_##PassClass, TC_NATIVE_PASS);          \
        }                                                                   \
    } _reg_instance_##PassClass

} // namespace termin
