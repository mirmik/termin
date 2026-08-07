#pragma once

#include "termin/editor/frame_graph_debugger_source.hpp"

#include <cstddef>
#include <functional>
#include <memory>

#include <termin/framegraph_remote/wire_codec.hpp>

namespace termin
{

    struct RemoteFrameGraphConnectionConfig
    {
        std::uint16_t port = 0;
        std::string authentication_token;
        std::size_t command_queue_capacity = 64;
        bool reconnect = true;
    };

    // Thread-safe editor projection of a remote topology session. Complete wire
    // messages are copied into immutable snapshots. On disconnect the most
    // recent topology remains visible and is explicitly marked stale.
    class RemoteFrameGraphDebuggerSource final
        : public IFrameGraphDebuggerSource
    {
    public:
        using CommandSender =
            std::function<bool(const framegraph_remote::Command&)>;

        explicit RemoteFrameGraphDebuggerSource(std::size_t gap_capacity = 64,
                                                CommandSender sender = {});
        ~RemoteFrameGraphDebuggerSource() override;

        std::shared_ptr<const FrameGraphDebuggerSnapshot>
        snapshot() const override;
        bool refresh() override;
        void finish_frame() override;
        void connect() override;
        void disconnect() override;
        void close() override;

        bool select_target(std::uint64_t target_id) override;
        bool select_pass(std::optional<std::uint64_t> pass_id) override;
        void set_mode(FrameGraphDebuggerMode mode) override;
        void set_selected_symbol(const std::string& symbol) override;
        void set_selected_resource(const std::string& resource) override;
        void set_channel_mode(int mode) override;
        void set_paused(bool paused) override;
        void set_highlight_hdr(bool enabled) override;
        std::string analyze_hdr() override;

        bool render_image(tgfx::RenderContext2& context,
                          tgfx::TextureHandle target,
                          FrameGraphDebuggerImageKind kind,
                          std::uint32_t width,
                          std::uint32_t height,
                          int channel_mode,
                          bool highlight_hdr) override;
        std::vector<std::uint8_t> read_depth_normalized(
            tgfx::IRenderDevice& device, int* width, int* height) override;

        bool ingest(const framegraph_remote::DecodedMessage& message);
        bool connect(RemoteFrameGraphConnectionConfig config);
        void transport_disconnected(std::string detail);

    private:
        class Impl;
        std::unique_ptr<Impl> impl_;
    };

} // namespace termin
