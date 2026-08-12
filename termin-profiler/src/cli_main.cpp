#include <csignal>
#include <exception>
#include <iostream>

#include <termin/profiler_app/cli.hpp>

namespace {
    volatile std::sig_atomic_t g_interrupted = 0;

    void handle_interrupt(int) {
        g_interrupted = 1;
    }
} // namespace

int main(int argc, char** argv) {
    try {
        const auto parsed = termin::profiler_app::parse_cli_options(argc, argv);
        if (!parsed.options) {
            std::cerr << "termin_profiler_cli: " << parsed.error << '\n' << termin::profiler_app::cli_usage();
            return static_cast<int>(termin::profiler_app::CliExitCode::Usage);
        }
        std::signal(SIGINT, handle_interrupt);
        return termin::profiler_app::run_cli(*parsed.options, {}, [] { return g_interrupted != 0; });
    } catch (const std::exception& error) {
        std::cerr << "termin_profiler_cli: fatal error: " << error.what() << '\n';
        return static_cast<int>(termin::profiler_app::CliExitCode::Runtime);
    } catch (...) {
        std::cerr << "termin_profiler_cli: fatal unknown error\n";
        return static_cast<int>(termin::profiler_app::CliExitCode::Runtime);
    }
}
