// inspect_registry_compat.hpp - Compatibility layer for termin::InspectRegistry
// This file provides termin:: namespace aliases for backward compatibility
// with existing code that uses termin::InspectRegistry.
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

// Re-export trent conversion functions
using tc::trent_to_tc_value;
using tc::tc_value_to_trent;
using tc::nb_to_trent_compat;
using tc::trent_to_nb_compat;

} // namespace termin

// Macros are already defined in tc_inspect.hpp
// INSPECT_FIELD and INSPECT_FIELD_CALLBACK
