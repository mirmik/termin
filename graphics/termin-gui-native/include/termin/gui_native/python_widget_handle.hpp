#pragma once

#include <termin/gui_native/tc_ui_document.h>

namespace termin::gui_native::python_bindings {

    // Shared by Python extension modules that exchange GUI widget handles.
    // The Python type itself is registered by termin.gui_native.
    struct WidgetHandle {
        tc_widget_handle handle = tc_widget_handle_invalid();
    };

} // namespace termin::gui_native::python_bindings
