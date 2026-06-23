#include "termin_python_backend.hpp"

#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

std::vector<std::string> tail_args(int argc, char** argv) {
    std::vector<std::string> result;
    for (int i = 1; i < argc; ++i) {
        result.emplace_back(argv[i]);
    }
    return result;
}

} // namespace

int main(int argc, char** argv) {
    try {
        termin_app::python_backend::configure_environment();
        std::vector<std::string> command =
            termin_app::python_backend::python_module_command("termin.module_warmup");
        std::vector<std::string> rest = tail_args(argc, argv);
        command.insert(command.end(), rest.begin(), rest.end());
        return termin_app::python_backend::run_process(command, "modules backend");
    } catch (const std::exception& exc) {
        std::cerr << "termin_modules_cli: " << exc.what() << "\n";
        return 2;
    }
}
