#include <termin/bootstrap/bootstrap.hpp>

#include <tcbase/tc_log.hpp>

namespace termin::bootstrap {

void init_python_kind_handlers(const RuntimeKindOptions&) {
    tc::Log::warn("[termin-bootstrap] Python kind handlers requested in a non-Python build");
}

void init_python_inspect_adapters() {
    tc::Log::warn("[termin-bootstrap] Python inspect adapters requested in a non-Python build");
}

void init_python_render_passes() {
    tc::Log::warn("[termin-bootstrap] Python render passes requested in a non-Python build");
}

void init_pointer_extractors() {
    tc::Log::warn("[termin-bootstrap] Python pointer extractors requested in a non-Python build");
}

void init_python_component_callbacks() {
    tc::Log::warn("[termin-bootstrap] Python component callbacks requested in a non-Python build");
}

} // namespace termin::bootstrap
