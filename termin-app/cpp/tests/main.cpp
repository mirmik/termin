#include "guard_main.h"

#include <termin/bootstrap/bootstrap.hpp>

#include <cstring>

int main(int argc, char** argv) {
    const char* test_filter = nullptr;
    for (int i = 1; i < argc; ++i) {
        const char* arg = argv[i];
        constexpr char prefix[] = "--test-case=";
        if (std::strncmp(arg, prefix, sizeof(prefix) - 1) == 0) {
            test_filter = arg + sizeof(prefix) - 1;
        } else if (std::strcmp(arg, "--test-case") == 0 && i + 1 < argc) {
            test_filter = argv[++i];
        } else if (std::strcmp(arg, "--verbose") == 0) {
            guard::test::set_verbose(true);
        }
    }

    termin::bootstrap::bootstrap_runtime();
    const int result = guard::test::run_all(test_filter);
    termin::bootstrap::shutdown_runtime();
    return result;
}
