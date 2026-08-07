#include <termin/bootstrap/bootstrap_c.h>

#include <cstdio>
#include <cstring>

#include <tcbase/tc_log.h>
#include <tgfx/resources/tc_shader_program_registry.h>
#include <tgfx/resources/tc_shader_registry.h>

namespace {

    int stale_shader_log_count = 0;

    void capture_log(tc_log_level level, const char* message) {
        if (level == TC_LOG_ERROR && message &&
            std::strstr(message, "stale resource handle dereference: type=tc_shader")) {
            ++stale_shader_log_count;
        }
    }

    bool load_program_payload() {
        tc_shader_program_handle handle =
            tc_shader_program_get_or_create("bootstrap-lifecycle-program", "Lifecycle Program");
        tc_shader_program* program = tc_shader_program_get(handle);
        if (!program) {
            std::fprintf(stderr, "failed to create shader program\n");
            return false;
        }

        const tc_shader_program_phase_desc phase = {"opaque", 0, tc_render_state_opaque()};
        const tc_shader_program_payload_desc payload = {
            "Lifecycle Program", nullptr, "slang", 1, nullptr, 0, &phase, 1};
        if (!tc_shader_program_set_payload(program, &payload)) {
            std::fprintf(stderr, "failed to set shader program payload\n");
            return false;
        }
        if (program->phase_count != 1 || !tc_shader_is_valid(program->phases[0].shader)) {
            std::fprintf(stderr, "shader program phase was not created\n");
            return false;
        }
        return true;
    }

} // namespace

int main() {
    tc_log_set_callback(capture_log);

    tc_init();
    const bool first_load_succeeded = load_program_payload();
    tc_shutdown();

    tc_init();
    const bool second_load_succeeded = load_program_payload();
    tc_shutdown();

    tc_log_set_callback(nullptr);
    if (stale_shader_log_count != 0) {
        std::fprintf(stderr, "observed %d stale shader handle errors\n", stale_shader_log_count);
    }
    return first_load_succeeded && second_load_succeeded && stale_shader_log_count == 0 ? 0 : 1;
}
