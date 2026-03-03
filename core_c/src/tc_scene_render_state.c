// tc_scene_render_state.c - Render scene state extension implementation
#include "core/tc_scene_render_state.h"
#include "core/tc_scene_extension.h"
#include "tc_value.h"
#include <stdlib.h>

static bool g_extension_registered = false;

void tc_scene_lighting_init(tc_scene_lighting* lighting) {
    if (!lighting) return;
    lighting->ambient_color[0] = 1.0f;
    lighting->ambient_color[1] = 1.0f;
    lighting->ambient_color[2] = 1.0f;
    lighting->ambient_intensity = 0.1f;
    lighting->shadow_method = TC_SHADOW_METHOD_PCF;
    lighting->shadow_softness = 1.0f;
    lighting->shadow_bias = 0.005f;
}

static bool value_to_float(const tc_value* v, float* out) {
    if (!v || !out) return false;
    switch (v->type) {
        case TC_VALUE_INT: *out = (float)v->data.i; return true;
        case TC_VALUE_FLOAT: *out = v->data.f; return true;
        case TC_VALUE_DOUBLE: *out = (float)v->data.d; return true;
        default: return false;
    }
}

static tc_value make_color3(float r, float g, float b) {
    tc_value list = tc_value_list_new();
    tc_value_list_push(&list, tc_value_double((double)r));
    tc_value_list_push(&list, tc_value_double((double)g));
    tc_value_list_push(&list, tc_value_double((double)b));
    return list;
}

static tc_value make_color4(float r, float g, float b, float a) {
    tc_value list = tc_value_list_new();
    tc_value_list_push(&list, tc_value_double((double)r));
    tc_value_list_push(&list, tc_value_double((double)g));
    tc_value_list_push(&list, tc_value_double((double)b));
    tc_value_list_push(&list, tc_value_double((double)a));
    return list;
}

static bool read_color3(const tc_value* v, float out_color[3]) {
    if (!v || v->type != TC_VALUE_LIST) return false;
    if (tc_value_list_size(v) < 3) return false;

    tc_value* c0 = tc_value_list_get((tc_value*)v, 0);
    tc_value* c1 = tc_value_list_get((tc_value*)v, 1);
    tc_value* c2 = tc_value_list_get((tc_value*)v, 2);
    if (!c0 || !c1 || !c2) return false;
    if (!value_to_float(c0, &out_color[0])) return false;
    if (!value_to_float(c1, &out_color[1])) return false;
    if (!value_to_float(c2, &out_color[2])) return false;
    return true;
}

static bool read_color4(const tc_value* v, float out_color[4]) {
    if (!v || v->type != TC_VALUE_LIST) return false;
    if (tc_value_list_size(v) < 4) return false;

    tc_value* c0 = tc_value_list_get((tc_value*)v, 0);
    tc_value* c1 = tc_value_list_get((tc_value*)v, 1);
    tc_value* c2 = tc_value_list_get((tc_value*)v, 2);
    tc_value* c3 = tc_value_list_get((tc_value*)v, 3);
    if (!c0 || !c1 || !c2 || !c3) return false;
    if (!value_to_float(c0, &out_color[0])) return false;
    if (!value_to_float(c1, &out_color[1])) return false;
    if (!value_to_float(c2, &out_color[2])) return false;
    if (!value_to_float(c3, &out_color[3])) return false;
    return true;
}

static void* render_state_create(tc_scene_handle scene, void* type_userdata) {
    (void)scene;
    (void)type_userdata;

    tc_scene_render_state* state = (tc_scene_render_state*)calloc(1, sizeof(tc_scene_render_state));
    if (!state) return NULL;

    tc_scene_lighting_init(&state->lighting);
    tc_scene_skybox_init(&state->skybox);
    state->background_color[0] = 0.0f;
    state->background_color[1] = 0.0f;
    state->background_color[2] = 0.0f;
    state->background_color[3] = 0.0f;
    return state;
}

static void render_state_destroy(void* ext, void* type_userdata) {
    (void)type_userdata;
    if (!ext) return;

    tc_scene_render_state* state = (tc_scene_render_state*)ext;
    tc_scene_skybox_free(&state->skybox);
    free(state);
}

static bool render_state_serialize(void* ext, tc_value* out_data, void* type_userdata) {
    (void)type_userdata;
    if (!ext || !out_data) return false;
    if (out_data->type != TC_VALUE_DICT) return false;

    tc_scene_render_state* state = (tc_scene_render_state*)ext;

    tc_value_dict_set(
        out_data,
        "background_color",
        make_color4(
            state->background_color[0],
            state->background_color[1],
            state->background_color[2],
            state->background_color[3]
        )
    );

    tc_value lighting = tc_value_dict_new();
    tc_value_dict_set(
        &lighting,
        "ambient_color",
        make_color3(
            state->lighting.ambient_color[0],
            state->lighting.ambient_color[1],
            state->lighting.ambient_color[2]
        )
    );
    tc_value_dict_set(&lighting, "ambient_intensity", tc_value_double((double)state->lighting.ambient_intensity));
    tc_value shadow = tc_value_dict_new();
    tc_value_dict_set(&shadow, "method", tc_value_int((int64_t)state->lighting.shadow_method));
    tc_value_dict_set(&shadow, "softness", tc_value_double((double)state->lighting.shadow_softness));
    tc_value_dict_set(&shadow, "bias", tc_value_double((double)state->lighting.shadow_bias));
    tc_value_dict_set(&lighting, "shadow_settings", shadow);
    tc_value_dict_set(out_data, "lighting", lighting);

    tc_value skybox = tc_value_dict_new();
    tc_value_dict_set(&skybox, "type", tc_value_int((int64_t)state->skybox.type));
    tc_value_dict_set(
        &skybox,
        "color",
        make_color3(state->skybox.color[0], state->skybox.color[1], state->skybox.color[2])
    );
    tc_value_dict_set(
        &skybox,
        "top_color",
        make_color3(state->skybox.top_color[0], state->skybox.top_color[1], state->skybox.top_color[2])
    );
    tc_value_dict_set(
        &skybox,
        "bottom_color",
        make_color3(state->skybox.bottom_color[0], state->skybox.bottom_color[1], state->skybox.bottom_color[2])
    );
    tc_value_dict_set(out_data, "skybox", skybox);

    return true;
}

static bool render_state_deserialize(void* ext, const tc_value* in_data, void* type_userdata) {
    (void)type_userdata;
    if (!ext || !in_data) return false;
    if (in_data->type != TC_VALUE_DICT) return false;

    tc_scene_render_state* state = (tc_scene_render_state*)ext;

    tc_value* bg = tc_value_dict_get((tc_value*)in_data, "background_color");
    if (bg) {
        read_color4(bg, state->background_color);
    }

    tc_value* lighting = tc_value_dict_get((tc_value*)in_data, "lighting");
    if (lighting && lighting->type == TC_VALUE_DICT) {
        tc_value* ambient_color = tc_value_dict_get(lighting, "ambient_color");
        if (ambient_color) {
            read_color3(ambient_color, state->lighting.ambient_color);
        }

        tc_value* ambient_intensity = tc_value_dict_get(lighting, "ambient_intensity");
        if (ambient_intensity) {
            value_to_float(ambient_intensity, &state->lighting.ambient_intensity);
        }

        tc_value* shadow = tc_value_dict_get(lighting, "shadow_settings");
        if (shadow && shadow->type == TC_VALUE_DICT) {
            tc_value* method = tc_value_dict_get(shadow, "method");
            tc_value* softness = tc_value_dict_get(shadow, "softness");
            tc_value* bias = tc_value_dict_get(shadow, "bias");
            if (method && method->type == TC_VALUE_INT) {
                state->lighting.shadow_method = (int)method->data.i;
            }
            if (softness) value_to_float(softness, &state->lighting.shadow_softness);
            if (bias) value_to_float(bias, &state->lighting.shadow_bias);
        }
    }

    tc_value* skybox = tc_value_dict_get((tc_value*)in_data, "skybox");
    if (skybox && skybox->type == TC_VALUE_DICT) {
        tc_value* type = tc_value_dict_get(skybox, "type");
        if (type && type->type == TC_VALUE_INT) {
            state->skybox.type = (int)type->data.i;
        }

        tc_value* color = tc_value_dict_get(skybox, "color");
        if (color) {
            read_color3(color, state->skybox.color);
        }
        tc_value* top_color = tc_value_dict_get(skybox, "top_color");
        if (top_color) {
            read_color3(top_color, state->skybox.top_color);
        }
        tc_value* bottom_color = tc_value_dict_get(skybox, "bottom_color");
        if (bottom_color) {
            read_color3(bottom_color, state->skybox.bottom_color);
        }
    }

    return true;
}

void tc_scene_render_state_extension_init(void) {
    if (g_extension_registered) return;

    tc_scene_ext_vtable vtable = {
        .create = render_state_create,
        .destroy = render_state_destroy,
        .serialize = render_state_serialize,
        .deserialize = render_state_deserialize,
    };

    if (!tc_scene_ext_register(
            TC_SCENE_EXT_TYPE_RENDER_STATE,
            "render_state",
            "render_state",
            &vtable,
            NULL
        )) {
        if (tc_scene_ext_is_registered(TC_SCENE_EXT_TYPE_RENDER_STATE)) {
            g_extension_registered = true;
            return;
        }
        return;
    }

    g_extension_registered = true;
}

tc_scene_render_state* tc_scene_render_state_get(tc_scene_handle scene) {
    return (tc_scene_render_state*)tc_scene_ext_get(scene, TC_SCENE_EXT_TYPE_RENDER_STATE);
}

bool tc_scene_render_state_ensure(tc_scene_handle scene) {
    if (tc_scene_ext_has(scene, TC_SCENE_EXT_TYPE_RENDER_STATE)) return true;
    return tc_scene_ext_attach(scene, TC_SCENE_EXT_TYPE_RENDER_STATE);
}
