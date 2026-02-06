// tc_editor_interaction_instance.cpp - EditorInteractionSystem singleton storage
// Compiled into entity_lib (SHARED) to ensure single instance across all DLLs

#include "editor/tc_editor_interaction.h"

// Global instance pointer
static tc_editor_interaction_system* g_editor_interaction_instance = nullptr;

extern "C" {

tc_editor_interaction_system* tc_editor_interaction_instance(void) {
    return g_editor_interaction_instance;
}

void tc_editor_interaction_set_instance(tc_editor_interaction_system* sys) {
    g_editor_interaction_instance = sys;
}

} // extern "C"
