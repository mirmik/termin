// tc_editor_interaction.h - EditorInteractionSystem C API for cross-DLL instance access
#ifndef TC_EDITOR_INTERACTION_H
#define TC_EDITOR_INTERACTION_H

#include "tc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// Opaque pointer to EditorInteractionSystem
typedef struct tc_editor_interaction_system tc_editor_interaction_system;

// Get global EditorInteractionSystem instance
TC_API tc_editor_interaction_system* tc_editor_interaction_instance(void);

// Set global EditorInteractionSystem instance
TC_API void tc_editor_interaction_set_instance(tc_editor_interaction_system* sys);

#ifdef __cplusplus
}
#endif

#endif // TC_EDITOR_INTERACTION_H
