#include "guard_main.h"

#include <stdexcept>

#include <termin/profiler_remote/desktop_target.hpp>

namespace {

    template <typename Exception, typename Callable> bool throws_as(Callable&& callable) {
        try {
            callable();
        } catch (const Exception&) {
            return true;
        } catch (...) {
            return false;
        }
        return false;
    }

} // namespace

TEST_CASE("desktop remote profiler requires explicit opt-in") {
    termin::profiler_remote::DesktopTargetEnvironment environment;
    environment.port = "46051";
    environment.authentication_token = "token";

    const auto config = termin::profiler_remote::make_desktop_target_config(environment, "termin_editor", "Test");

    CHECK_FALSE(config.has_value());
}

TEST_CASE("desktop remote profiler validates enabled configuration") {
    termin::profiler_remote::DesktopTargetEnvironment environment;
    environment.enabled = "true";
    environment.authentication_token = "token";
    CHECK(throws_as<std::invalid_argument>(
        [&]() { (void)termin::profiler_remote::make_desktop_target_config(environment, "termin_editor", "Test"); }));

    environment.port = "70000";
    CHECK(throws_as<std::invalid_argument>(
        [&]() { (void)termin::profiler_remote::make_desktop_target_config(environment, "termin_editor", "Test"); }));

    environment.port = "46051";
    environment.authentication_token = "";
    CHECK(throws_as<std::invalid_argument>(
        [&]() { (void)termin::profiler_remote::make_desktop_target_config(environment, "termin_editor", "Test"); }));
}

TEST_CASE("desktop remote profiler builds loopback host identity") {
    termin::profiler_remote::DesktopTargetEnvironment environment;
    environment.enabled = "on";
    environment.port = "46051";
    environment.authentication_token = "session-token";

    const auto config = termin::profiler_remote::make_desktop_target_config(environment, "termin_player", "Debug");

    REQUIRE(config.has_value());
    CHECK_EQ(config->bind_address, "127.0.0.1");
    CHECK_EQ(config->port, 46051);
    CHECK_EQ(config->authentication_token, "session-token");
    CHECK_EQ(config->build_type, "Debug");
    CHECK_EQ(config->build_id, "termin_player");
    CHECK(config->process_id > 0);
}

GUARD_TEST_MAIN();
