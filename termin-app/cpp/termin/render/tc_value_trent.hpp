// tc_value_trent.hpp - Conversion between tc_value (C) and nos::trent (C++)
#pragma once

#include <trent/trent.h>

extern "C" {
#include "tc_value.h"
}

namespace tc {

// Convert trent → tc_value (for storing parsed JSON in C)
tc_value trent_to_tc_value(const nos::trent& t);

// Convert tc_value → trent (for graph_compiler)
nos::trent tc_value_to_trent(const tc_value& v);

} // namespace tc
