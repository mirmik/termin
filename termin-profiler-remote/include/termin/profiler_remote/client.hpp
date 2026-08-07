#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <string>

#include <termin/profiler_remote/wire_codec.hpp>

namespace termin::profiler_remote {

    struct ClientConfig {
        std::string address = "127.0.0.1";
        std::uint16_t port = 0;
        std::string authentication_token;
        std::size_t command_queue_capacity = 64;
        bool reconnect = true;
    };

    struct ClientStatus {
        bool running = false;
        bool connected = false;
        std::uint64_t connection_attempts = 0;
        std::uint64_t sessions = 0;
        std::uint64_t rejected_commands = 0;
    };

    class TERMIN_PROFILER_REMOTE_API RemoteProfilerClient {
    public:
        using MessageHandler = std::function<void(const DecodedMessage&)>;
        using DisconnectHandler = std::function<void(std::string detail)>;

        RemoteProfilerClient(ClientConfig config,
                             MessageHandler message_handler,
                             DisconnectHandler disconnect_handler = {});
        ~RemoteProfilerClient();
        RemoteProfilerClient(const RemoteProfilerClient&) = delete;
        RemoteProfilerClient& operator=(const RemoteProfilerClient&) = delete;

        bool start();
        void stop();
        bool send_control(const Control& control);
        ClientStatus status() const;

    private:
        class Impl;
        std::unique_ptr<Impl> impl_;
    };

} // namespace termin::profiler_remote
