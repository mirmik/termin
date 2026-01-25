#pragma once

// CxxPass - Base class for C++ render passes
// Same pattern as CxxComponent: embedded tc_pass with virtual dispatch

#include <string>
#include <set>
#include <vector>
#include <cstddef>
#include <unordered_map>

#include "termin/render/execute_context.hpp"
#include "termin/render/resource_spec.hpp"

extern "C" {
#include "tc_pass.h"
}

namespace termin {

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
// Pass Registration (same pattern as ComponentRegistrar)
// ============================================================================

// Factory data stored in static variables per template instantiation
template<typename T>
struct CxxPassFactoryData {
    static const char* type_name;

    static tc_pass* create(void* /*userdata*/) {
        T* pass = new T();
        tc_pass* c = pass->c_pass();

        // Link to type registry
        tc_type_entry* entry = tc_pass_registry_get_entry(type_name);
        if (entry) {
            c->type_entry = entry;
            c->type_version = entry->version;
        }

        return c;
    }
};

template<typename T> const char* CxxPassFactoryData<T>::type_name = nullptr;

// Helper for static registration of C++ passes
template<typename T>
struct PassRegistrar {
    PassRegistrar(const char* name) {
        // Store type name for factory
        CxxPassFactoryData<T>::type_name = name;

        // Register in C registry with static factory function
        tc_pass_registry_register(
            name,
            &CxxPassFactoryData<T>::create,
            nullptr,
            TC_NATIVE_PASS
        );
    }
};

// Macro for registering C++ passes
// Place after class definition
//
// Usage:
//   REGISTER_PASS(ColorPass);
//   REGISTER_PASS(ShadowPass);
#define REGISTER_PASS(ClassName) \
    static ::termin::PassRegistrar<ClassName> \
        _pass_registrar_##ClassName(#ClassName)

} // namespace termin
