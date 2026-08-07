#pragma once

#include "termin/editor/frame_profiler_source.hpp"

#include <functional>
#include <memory>

#include <termin/profiler_remote/client.hpp>
#include <termin/profiler_remote/wire_codec.hpp>

namespace termin {

    // Editor-thread adapter shared by recorded replay and the live TCP receiver.
    // ingest() commits a complete new immutable snapshot or leaves the prior state
    // untouched on error. A live receiver supplies a bounded command sender.
    class RemoteFrameProfilerSource final : public IFrameProfilerSource {
    public:
        using CommandSender = std::function<bool(const profiler_remote::Control& control)>;

        explicit RemoteFrameProfilerSource(std::size_t capacity, CommandSender sender = {});
        ~RemoteFrameProfilerSource() override;

        std::uint64_t revision() const override;
        std::shared_ptr<const FrameProfilerSnapshot> snapshot() override;
        bool start_capture() override;
        bool pause_capture() override;
        bool set_section_profiling(bool enabled) override;
        bool clear_capture() override;
        bool set_include_ui(bool enabled) override;
        void close() override;

        bool ingest(const profiler_remote::DecodedMessage& message);
        bool connect(profiler_remote::ClientConfig config);
        void disconnect();
        void transport_disconnected(std::string detail);

    private:
        class Impl;
        std::unique_ptr<Impl> impl_;
    };

} // namespace termin
