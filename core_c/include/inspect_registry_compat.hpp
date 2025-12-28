// inspect_registry_compat.hpp - Compatibility layer for termin::InspectRegistry
// This file provides termin:: namespace aliases for backward compatibility
// with existing code that uses termin::InspectRegistry.
//
// Migration: Replace #include "inspect/inspect_registry.hpp"
//            with    #include <inspect_registry_compat.hpp>
//
// Define TC_HAS_TRENT before including if you need trent compatibility.
//
#pragma once

#include "tc_inspect.hpp"

namespace termin {

// Re-export types from tc namespace
using TypeBackend = tc::TypeBackend;
using EnumChoice = tc::EnumChoice;
using InspectFieldInfo = tc::InspectFieldInfo;
using KindHandler = tc::KindHandler;
using InspectRegistry = tc::InspectRegistry;

// Re-export registration helpers
template<typename C, typename T>
using InspectFieldRegistrar = tc::InspectFieldRegistrar<C, T>;

template<typename C, typename T>
using InspectFieldCallbackRegistrar = tc::InspectFieldCallbackRegistrar<C, T>;

#ifdef TC_HAS_TRENT
// Re-export trent conversion functions
using tc::trent_to_tc_value;
using tc::tc_value_to_trent;
using tc::py_to_trent_compat;
using tc::trent_to_py_compat;
#endif

} // namespace termin

// Macros are already defined in tc_inspect.hpp
// INSPECT_FIELD and INSPECT_FIELD_CALLBACK
