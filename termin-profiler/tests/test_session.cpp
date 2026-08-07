#include "guard_main.h"

#include <string>

#include <termin/profiler_app/session.hpp>

using termin::profiler_app::RemoteProfilerSession;

TEST_CASE("Standalone profiler validates endpoint without exposing token") {
    RemoteProfilerSession session(32);

    CHECK(!session.connect("", "secret-token"));
    CHECK(session.connection_model()->text().find("Port") != std::string::npos);
    CHECK(session.connection_model()->text().find("secret-token") == std::string::npos);

    CHECK(!session.connect("0", "secret-token"));
    CHECK(!session.connect("65536", "secret-token"));
    CHECK(!session.connect("not-a-port", "secret-token"));
    CHECK(!session.connect("46051", ""));
    CHECK(session.connection_model()->text().find("Token") != std::string::npos);
}

TEST_CASE("Standalone profiler connection lifecycle is idempotent") {
    RemoteProfilerSession session(32);

    CHECK(session.connect("65534", "lifecycle-token"));
    CHECK(session.connection_requested());
    CHECK_EQ(session.port(), 65534);
    CHECK(session.connection_model()->text().find("lifecycle-token") == std::string::npos);

    session.disconnect();
    CHECK(!session.connection_requested());
    CHECK_EQ(session.port(), 0);
    CHECK(session.connection_model()->text().find("Disconnected") != std::string::npos);

    session.disconnect();
    session.close();
    session.close();
    CHECK(session.connection_model()->text().find("closed") != std::string::npos);
}

GUARD_TEST_MAIN();
