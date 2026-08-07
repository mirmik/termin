#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <string>

#include <termin/framegraph_remote/wire_codec.hpp>

#if defined(_WIN32) && defined(TERMIN_FRAMEGRAPH_REMOTE_CLIENT_EXPORTS)
#define TERMIN_FRAMEGRAPH_REMOTE_CLIENT_API __declspec(dllexport)
#elif defined(_WIN32)
#define TERMIN_FRAMEGRAPH_REMOTE_CLIENT_API __declspec(dllimport)
#else
#define TERMIN_FRAMEGRAPH_REMOTE_CLIENT_API                                    \
    __attribute__((visibility("default")))
#endif

namespace termin::framegraph_remote_client
{

    struct ClientConfig
    {
        std::string address = "127.0.0.1";
        std::uint16_t port = 0;
        std::string authentication_token;
        std::size_t command_queue_capacity = 64;
        bool reconnect = true;
    };

    struct ClientStatus
    {
        bool running = false;
        bool connected = false;
        std::uint64_t connection_attempts = 0;
        std::uint64_t sessions = 0;
        std::uint64_t rejected_commands = 0;
    };

    // The client owns one network thread. send_command() has a single-producer
    // contract and is intended to be called from the editor thread. Callbacks
    // run on the network thread and must not access editor or rendering state
    // directly.
    class TERMIN_FRAMEGRAPH_REMOTE_CLIENT_API RemoteFrameGraphClient
    {
    public:
        using MessageHandler =
            std::function<void(const framegraph_remote::DecodedMessage&)>;
        using DisconnectHandler = std::function<void(std::string detail)>;

        RemoteFrameGraphClient(ClientConfig config,
                               MessageHandler message_handler,
                               DisconnectHandler disconnect_handler = {});
        ~RemoteFrameGraphClient();

        RemoteFrameGraphClient(const RemoteFrameGraphClient&) = delete;
        RemoteFrameGraphClient&
        operator=(const RemoteFrameGraphClient&) = delete;

        bool start();
        void stop();
        bool send_command(const framegraph_remote::Command& command);
        ClientStatus status() const;

    private:
        class Impl;
        std::unique_ptr<Impl> impl_;
    };

} // namespace termin::framegraph_remote_client
