#pragma once

#include <termin_modules/module_runtime.hpp>

#include "termin/render/render_export.hpp"

namespace termin {

class RENDER_API TermModulesIntegration {
public:
    termin_modules::ModuleEnvironment _environment;

public:
    void set_environment(termin_modules::ModuleEnvironment environment);
    const termin_modules::ModuleEnvironment& environment() const;
    void configure_runtime(termin_modules::ModuleRuntime& runtime) const;
};

} // namespace termin
