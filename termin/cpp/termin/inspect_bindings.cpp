// inspect_bindings.cpp — termin domain-specific inspect wiring
// Core types (TypeBackend, InspectRegistry, etc.) live in _inspect_native.
// This file imports them and adds domain-specific init + ptr extractors.

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <cstdint>

#include <termin/entity/component.hpp>
#include "material/tc_material_handle.hpp"
#include "inspect/tc_inspect_init.h"
#include "render/frame_pass.hpp"
#include "inspect_bindings.hpp"

namespace nb = nanobind;

namespace termin {

void bind_inspect(nb::module_& m) {
    // Domain-specific init (must run before types are used)
    tc_inspect_kind_core_init();
    tc_inspect_component_adapter_init();
    tc_inspect_pass_adapter_init();
    tc_inspect_python_adapter_init();

    // Import _inspect_native — types are registered there
    nb::module_ inspect_native = nb::module_::import_("termin.inspect._inspect_native");

    // Re-export all types into termin._native.inspect submodule
    m.attr("TypeBackend") = inspect_native.attr("TypeBackend");
    m.attr("EnumChoice") = inspect_native.attr("EnumChoice");
    m.attr("InspectFieldInfo") = inspect_native.attr("InspectFieldInfo");
    m.attr("InspectRegistry") = inspect_native.attr("InspectRegistry");
    m.attr("inspect_registry_address") = inspect_native.attr("inspect_registry_address");
    m.attr("kind_registry_cpp_address") = inspect_native.attr("kind_registry_cpp_address");

    // Register domain-specific pointer extractors
    nb::object register_fn = inspect_native.attr("register_ptr_extractor");

    // Component* extractor (C++ component types: MeshRenderer, etc.)
    register_fn(nb::cpp_function([](nb::object obj) -> nb::object {
        try {
            void* ptr = static_cast<void*>(nb::cast<Component*>(obj));
            return nb::int_(reinterpret_cast<uintptr_t>(ptr));
        } catch (const nb::cast_error&) {
            return nb::none();
        }
    }));

    // TcMaterial extractor (handle-based)
    register_fn(nb::cpp_function([](nb::object obj) -> nb::object {
        try {
            TcMaterial mat = nb::cast<TcMaterial>(obj);
            return nb::int_(reinterpret_cast<uintptr_t>(mat.get()));
        } catch (const nb::cast_error&) {
            return nb::none();
        }
    }));

    // CxxFramePass* extractor (ColorPass, ShadowPass, etc.)
    register_fn(nb::cpp_function([](nb::object obj) -> nb::object {
        try {
            void* ptr = static_cast<void*>(nb::cast<CxxFramePass*>(obj));
            return nb::int_(reinterpret_cast<uintptr_t>(ptr));
        } catch (const nb::cast_error&) {
            return nb::none();
        }
    }));
}

} // namespace termin
