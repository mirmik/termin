#pragma once

#include <memory>
#include <optional>
#include <string>

#include <termin/profiler_remote/target_service.hpp>

namespace termin::profiler_remote
{

    struct DesktopTargetEnvironment
    {
        std::optional<std::string> enabled;
        std::optional<std::string> bind_address;
        std::optional<std::string> port;
        std::optional<std::string> authentication_token;
    };

    // Read the process-wide opt-in contract used by native desktop hosts.
    // TERMIN_REMOTE_PROFILER must be explicitly enabled; address defaults to
    // loopback, while port and token are mandatory when enabled.
    TERMIN_PROFILER_REMOTE_API DesktopTargetEnvironment
    read_desktop_target_environment();

    // Convert the environment-shaped values into a validated target config.
    // Exposed separately so hosts and tests can validate configuration without
    // opening a listener.
    TERMIN_PROFILER_REMOTE_API std::optional<TargetServiceConfig>
    make_desktop_target_config(const DesktopTargetEnvironment& environment,
                               std::string host_name,
                               std::string build_type,
                               std::string build_id = {});

    // Start the optional desktop target. Returns null when the explicit opt-in
    // is absent or disabled; invalid enabled configuration throws after
    // logging.
    TERMIN_PROFILER_REMOTE_API std::shared_ptr<RemoteProfilerTarget>
    start_desktop_target_from_environment(std::string host_name,
                                          std::string build_type,
                                          std::string build_id = {});

} // namespace termin::profiler_remote
