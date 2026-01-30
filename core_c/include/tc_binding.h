// tc_binding.h - Language binding type definitions
// Shared between tc_component.h and tc_pass.h
#ifndef TC_BINDING_H
#define TC_BINDING_H

// ============================================================================
// Language enum - which language a type is defined in
// Also used as index for bindings[] array
// ============================================================================

typedef enum tc_language {
    TC_LANGUAGE_C = 0,
    TC_LANGUAGE_CXX = 1,
    TC_LANGUAGE_PYTHON = 2,
    TC_LANGUAGE_RUST = 3,
    TC_LANGUAGE_CSHARP = 4,
    TC_LANGUAGE_MAX = 8
} tc_language;

#endif // TC_BINDING_H
