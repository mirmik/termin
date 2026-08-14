#include <termin/bootstrap/bootstrap.hpp>
#include <termin/bootstrap/bootstrap_c.h>

#include <render/tc_pass.h>
#include <tc_inspect_cpp.hpp>
#include <termin/materials/surface_contract_registry.h>

#include <cstdio>

namespace {

    bool require(bool condition, const char* message) {
        if (!condition) {
            std::fprintf(stderr, "explicit pass bootstrap contract failed: %s\n", message);
        }
        return condition;
    }

} // namespace

int main() {
    bool ok = true;
    auto& inspect = tc::InspectRegistry::instance();

    ok &= require(!tc_pass_registry_has("ColorPass"), "linking built-in libraries must not register ColorPass");
    ok &= require(!tc_pass_registry_has("MaterialPass"), "linking built-in libraries must not register MaterialPass");
    const tc_surface_contract_key standard_surface = {
        TC_STANDARD_PBR_SURFACE_CONTRACT_ID,
        TC_STANDARD_PBR_SURFACE_CONTRACT_VERSION,
    };
    ok &= require(tc_surface_contract_registry_find(standard_surface) == nullptr,
                  "linking material libraries must not register surface contracts");
    ok &= require(inspect.find_field("ColorPass", "output_res") == nullptr,
                  "including/loading ColorPass must not register inspect fields");

    tc_bootstrap_runtime();
    const size_t first_count = tc_pass_registry_type_count();
    ok &= require(tc_pass_registry_has("ColorPass"), "bootstrap must register ColorPass factory");
    ok &= require(tc_pass_registry_has("MaterialPass"), "bootstrap must register MaterialPass factory");
    ok &= require(inspect.find_field("ColorPass", "output_res") != nullptr,
                  "ColorPass::register_type must register inspect fields");
    ok &= require(inspect.find_field("MaterialPass", "texture_resources") != nullptr,
                  "MaterialPass::register_type must register serializable fields");
    ok &= require(tc_surface_contract_registry_find(standard_surface) != nullptr,
                  "bootstrap must register the standard PBR surface contract");

    tc_bootstrap_runtime();
    ok &= require(tc_pass_registry_type_count() == first_count, "repeated bootstrap must be idempotent");

    termin::bootstrap::shutdown_runtime();
    ok &= require(!tc_pass_registry_has("ColorPass"), "shutdown must clear built-in pass factories");
    ok &= require(tc_runtime_type_registry_type_count() == 0,
                  "shutdown must clear runtime type records before intern cleanup");
    ok &= require(tc_surface_contract_registry_find(standard_surface) == nullptr,
                  "shutdown must invalidate surface contract lookup");

    termin::bootstrap::bootstrap_runtime();
    ok &= require(tc_pass_registry_has("ColorPass"), "pass types must register again after shutdown");
    ok &= require(tc_surface_contract_registry_find(standard_surface) != nullptr,
                  "surface contracts must register again after shutdown");
    termin::bootstrap::shutdown_runtime();
    ok &= require(tc_runtime_type_registry_type_count() == 0, "second shutdown must clear runtime type records");

    termin::bootstrap::bootstrap_runtime();
    ok &= require(tc_pass_registry_has("ColorPass"), "pass types must survive a third bootstrap after two shutdowns");
    ok &= require(tc_pass_registry_has("MaterialPass"), "third bootstrap must rebuild component render pass factories");
    termin::bootstrap::shutdown_runtime();
    return ok ? 0 : 1;
}
