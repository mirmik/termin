#include "termin_visual_scene/tc_visual_annotation3d.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#include <tcbase/tc_log.h>

typedef struct tc_annotation_item {
    tc_visual_item3d item;
    tc_visual_annotation3d* commands;
    size_t count;
} tc_annotation_item;

static void destroy_annotation(tc_visual_item3d* base) {
    tc_annotation_item* item = base->body;
    free(item->commands);
    free(item);
}

static bool paint_annotation(const tc_visual_item3d* base, tc_visual_item_paint_context3d* context) {
    const tc_annotation_item* item = base->body;
    if (!item->count)
        return true;
    const tc_visual_annotation_packet3d packet = {item->commands, item->count};
    return tc_visual_item_paint_context3d_submit(context, TC_VISUAL_ANNOTATION_PROTOCOL_3D, &packet, sizeof(packet));
}

static const tc_visual_item3d_vtable annotation_vtable = {
    .type_name = "termin.visual.Annotation3D",
    .paint = paint_annotation,
};

tc_visual_item3d_handle tc_visual_annotation_item3d_create(tc_visual_scene3d_handle scene) {
    if (!tc_visual_scene3d_is_valid(scene)) {
        tc_log_error("Cannot create annotation item in an invalid visual scene");
        return tc_visual_item3d_handle_invalid();
    }
    tc_annotation_item* item = calloc(1, sizeof(*item));
    if (!item) {
        tc_log_error("Cannot allocate annotation item");
        return tc_visual_item3d_handle_invalid();
    }
    tc_visual_item3d_init_unowned(&item->item, &annotation_vtable, TC_LANGUAGE_C, item);
    return tc_visual_scene3d_adopt_item(scene, &item->item, destroy_annotation);
}

static bool positive_finite(float value) {
    return isfinite(value) && value > 0.0f;
}

static bool valid_annotation(const tc_visual_annotation3d* command) {
    int anchors;
    switch (command->kind) {
    case TC_VISUAL_ANNOTATION_LINE:
    case TC_VISUAL_ANNOTATION_ARROW:
        if (!positive_finite(command->width_dip) ||
            (command->kind == TC_VISUAL_ANNOTATION_ARROW && !positive_finite(command->head_dip)))
            return false;
        anchors = 2;
        break;
    case TC_VISUAL_ANNOTATION_DISC:
    case TC_VISUAL_ANNOTATION_RING:
        if (!positive_finite(command->radius_dip) ||
            (command->kind == TC_VISUAL_ANNOTATION_RING && !positive_finite(command->width_dip)))
            return false;
        anchors = 1;
        break;
    case TC_VISUAL_ANNOTATION_QUAD:
        anchors = 4;
        break;
    default:
        return false;
    }
    for (int i = 0; i < anchors; ++i) {
        for (int axis = 0; axis < 3; ++axis) {
            if (!isfinite(command->points[i][axis]))
                return false;
        }
    }
    return true;
}

bool tc_visual_annotation_item3d_set(tc_visual_scene3d_handle scene,
                                     tc_visual_item3d_handle handle,
                                     const tc_visual_annotation3d* commands,
                                     size_t count) {
    tc_visual_item3d* base = tc_visual_scene3d_resolve_item(scene, handle);
    if (!base || base->vtable != &annotation_vtable || (!commands && count) || count > SIZE_MAX / sizeof(*commands)) {
        tc_log_error("Cannot replace annotation batch: invalid item or command array");
        return false;
    }
    for (size_t i = 0; i < count; ++i) {
        if (!valid_annotation(&commands[i])) {
            tc_log_error("Invalid visual annotation at index %zu", i);
            return false;
        }
    }
    tc_visual_annotation3d* replacement = NULL;
    if (count) {
        replacement = malloc(count * sizeof(*replacement));
        if (!replacement) {
            tc_log_error("Cannot allocate annotation batch of %zu commands", count);
            return false;
        }
        memcpy(replacement, commands, count * sizeof(*replacement));
    }
    tc_annotation_item* item = base->body;
    free(item->commands);
    item->commands = replacement;
    item->count = count;
    return true;
}
