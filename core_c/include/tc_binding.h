// tc_binding.h - Language binding type definitions
// Shared between tc_component.h and tc_pass.h
#ifndef TC_BINDING_H
#define TC_BINDING_H

// ============================================================================
// Language enum - which language a type is defined in
// ============================================================================

typedef enum tc_language {
    TC_LANGUAGE_C = 0,
    TC_LANGUAGE_CXX = 1,
    TC_LANGUAGE_PYTHON = 2,
    TC_LANGUAGE_RUST = 3,
    TC_LANGUAGE_CSHARP = 4
} tc_language;

// ============================================================================
// Binding types - for language-specific wrappers (accessing objects from other languages)
// ============================================================================

#define TC_BINDING_NONE 0
#define TC_BINDING_PYTHON 1
#define TC_BINDING_CSHARP 2
#define TC_BINDING_RUST 3
#define TC_BINDING_MAX 8

#endif // TC_BINDING_H
