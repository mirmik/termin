#include <exception>
#include <iostream>

#include <termin/profiler_app/cli.hpp>

int main(int argc, char** argv) {
    try {
        const auto parsed = termin::profiler_app::parse_cli_options(argc, argv);
        if (!parsed.options) {
            std::cerr << "termin_profiler_cli: " << parsed.error << '\n' << termin::profiler_app::cli_usage();
            return static_cast<int>(termin::profiler_app::CliExitCode::Usage);
        }
        return termin::profiler_app::run_cli(*parsed.options);
    } catch (const std::exception& error) {
        std::cerr << "termin_profiler_cli: fatal error: " << error.what() << '\n';
        return static_cast<int>(termin::profiler_app::CliExitCode::Runtime);
    } catch (...) {
        std::cerr << "termin_profiler_cli: fatal unknown error\n";
        return static_cast<int>(termin::profiler_app::CliExitCode::Runtime);
    }
}
