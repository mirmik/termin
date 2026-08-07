#include <termin/profiler_remote/desktop_target.hpp>

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <limits>
#include <stdexcept>
#include <string_view>
#include <utility>

#include <tcbase/tc_log.h>

#ifdef _WIN32
#include <process.h>
#else
#include <unistd.h>
#endif

namespace termin::profiler_remote {
    namespace {

        std::optional<std::string> environment_value(const char* name) {
            const char* value = std::getenv(name);
            if (value == nullptr) {
                return std::nullopt;
            }
            return std::string(value);
        }

        std::string normalized_flag(std::string value) {
            value.erase(
                std::remove_if(value.begin(), value.end(), [](unsigned char ch) { return std::isspace(ch) != 0; }),
                value.end());
            std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
                return static_cast<char>(std::tolower(ch));
            });
            return value;
        }

        bool parse_enabled(const std::optional<std::string>& value) {
            if (!value) {
                return false;
            }
            const std::string normalized = normalized_flag(*value);
            if (normalized == "1" || normalized == "true" || normalized == "yes" || normalized == "on") {
                return true;
            }
            if (normalized == "0" || normalized == "false" || normalized == "no" || normalized == "off" ||
                normalized.empty()) {
                return false;
            }
            throw std::invalid_argument("TERMIN_REMOTE_PROFILER must be a boolean flag");
        }

        std::uint16_t parse_port(const std::optional<std::string>& value) {
            if (!value || value->empty()) {
                throw std::invalid_argument("TERMIN_REMOTE_PROFILER_PORT is required when remote "
                                            "profiling is enabled");
            }
            try {
                std::size_t consumed = 0;
                const unsigned long parsed = std::stoul(*value, &consumed, 10);
                if (consumed != value->size() || parsed == 0 || parsed > std::numeric_limits<std::uint16_t>::max()) {
                    throw std::invalid_argument("invalid port");
                }
                return static_cast<std::uint16_t>(parsed);
            } catch (const std::exception&) {
                throw std::invalid_argument("TERMIN_REMOTE_PROFILER_PORT must "
                                            "be in the range 1..65535");
            }
        }

        std::string desktop_platform() {
#ifdef _WIN32
            return "Windows";
#elif defined(__APPLE__)
            return "macOS";
#elif defined(__linux__)
            return "Linux";
#else
            return "Desktop";
#endif
        }

        std::string desktop_abi() {
#if defined(__x86_64__) || defined(_M_X64)
            return "x86_64";
#elif defined(__aarch64__) || defined(_M_ARM64)
            return "arm64";
#elif defined(__i386__) || defined(_M_IX86)
            return "x86";
#elif defined(__arm__) || defined(_M_ARM)
            return "arm";
#else
            return "unknown";
#endif
        }

        std::uint32_t process_id() {
#ifdef _WIN32
            return static_cast<std::uint32_t>(_getpid());
#else
            return static_cast<std::uint32_t>(getpid());
#endif
        }

    } // namespace

    DesktopTargetEnvironment read_desktop_target_environment() {
        return DesktopTargetEnvironment{
            environment_value("TERMIN_REMOTE_PROFILER"),
            environment_value("TERMIN_REMOTE_PROFILER_ADDRESS"),
            environment_value("TERMIN_REMOTE_PROFILER_PORT"),
            environment_value("TERMIN_REMOTE_PROFILER_TOKEN"),
        };
    }

    std::optional<TargetServiceConfig> make_desktop_target_config(const DesktopTargetEnvironment& environment,
                                                                  std::string host_name,
                                                                  std::string build_type,
                                                                  std::string build_id) {
        if (!parse_enabled(environment.enabled)) {
            return std::nullopt;
        }
        if (host_name.empty()) {
            throw std::invalid_argument("desktop remote profiler host name is empty");
        }
        if (!environment.authentication_token || environment.authentication_token->empty()) {
            throw std::invalid_argument("TERMIN_REMOTE_PROFILER_TOKEN is required when remote "
                                        "profiling is enabled");
        }

        TargetServiceConfig config;
        config.bind_address = environment.bind_address.value_or("127.0.0.1");
        config.port = parse_port(environment.port);
        config.authentication_token = *environment.authentication_token;
        config.platform = desktop_platform();
        config.abi = desktop_abi();
        config.build_type = std::move(build_type);
        config.build_id = build_id.empty() ? std::move(host_name) : std::move(build_id);
        config.process_id = process_id();
        return config;
    }

    std::shared_ptr<RemoteProfilerTarget>
    start_desktop_target_from_environment(std::string host_name, std::string build_type, std::string build_id) {
        try {
            auto config = make_desktop_target_config(
                read_desktop_target_environment(), std::move(host_name), std::move(build_type), std::move(build_id));
            if (!config) {
                return nullptr;
            }

            const std::string bind_address = config->bind_address;
            auto target = std::make_shared<RemoteProfilerTarget>(std::move(*config));
            if (!target->start()) {
                throw std::runtime_error("listener start failed");
            }
            const TargetServiceStatus status = target->status();
            tc_log_info("desktop remote profiler target: enabled on %s:%u",
                        bind_address.c_str(),
                        static_cast<unsigned>(status.listening_port));
            return target;
        } catch (const std::exception& error) {
            tc_log_error("desktop remote profiler target: %s", error.what());
            throw;
        }
    }

} // namespace termin::profiler_remote
