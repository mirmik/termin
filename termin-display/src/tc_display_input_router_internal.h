#pragma once

#include "render/tc_input_manager.h"

typedef struct tc_display tc_display;

tc_input_manager* tc_display_input_router_create(tc_display* display);
void tc_display_input_router_destroy(tc_input_manager* endpoint);
