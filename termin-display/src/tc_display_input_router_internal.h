#pragma once

#include "render/tc_input_manager.h"
#include "render/tc_display_pool.h"

tc_input_manager* tc_display_input_router_create(tc_display_handle display);
void tc_display_input_router_destroy(tc_input_manager* endpoint);
