#include "termin/editor/remote_frame_graph_debugger_source.hpp"

#include <termin/framegraph_remote_client/client.hpp>

#include <algorithm>
#include <chrono>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <unordered_map>
#include <utility>
#include <variant>

#include <tcbase/tc_log.h>

namespace termin
{
    namespace
    {

        using namespace framegraph_remote;
        using Clock = std::chrono::steady_clock;

        framegraph_remote_client::ClientConfig
        project_client_config(RemoteFrameGraphConnectionConfig config)
        {
            framegraph_remote_client::ClientConfig result;
            result.port = config.port;
            result.authentication_token =
                std::move(config.authentication_token);
            result.command_queue_capacity = config.command_queue_capacity;
            result.reconnect = config.reconnect;
            return result;
        }

        FrameGraphDebuggerState project_state(SessionState state)
        {
            switch (state)
            {
            case SessionState::waiting_capture:
                return FrameGraphDebuggerState::WaitingFrame;
            case SessionState::suspended:
                return FrameGraphDebuggerState::Suspended;
            case SessionState::error:
                return FrameGraphDebuggerState::Error;
            case SessionState::idle:
            case SessionState::waiting_topology:
            case SessionState::streaming:
                return FrameGraphDebuggerState::Bound;
            }
            return FrameGraphDebuggerState::Error;
        }

        std::string topology_summary(const TopologySnapshot& topology)
        {
            std::ostringstream stream;
            stream << "Remote graph revision " << topology.graph_revision
                   << ": " << topology.passes.size() << " passes, "
                   << topology.resources.size() << " resources\nSchedule:";
            for (std::uint64_t id : topology.schedule)
                stream << ' ' << id;
            return stream.str();
        }

        std::string pass_summary(const FrameGraphDebuggerPassSnapshot* pass)
        {
            if (!pass)
                return {};
            std::ostringstream stream;
            stream << "{\n  \"id\": " << pass->id
                   << ",\n  \"authored_index\": " << pass->authored_index
                   << ",\n  \"name\": \"" << pass->name << "\",\n  \"type\": \""
                   << pass->type << "\",\n  \"enabled\": "
                   << (pass->enabled ? "true" : "false")
                   << ",\n  \"passthrough\": "
                   << (pass->passthrough ? "true" : "false") << "\n}";
            return stream.str();
        }

    } // namespace

    class RemoteFrameGraphDebuggerSource::Impl
    {
    public:
        Impl(std::size_t target_gap_capacity, CommandSender target_sender)
            : gap_capacity(target_gap_capacity),
              sender(std::move(target_sender))
        {
            if (gap_capacity == 0)
            {
                throw std::invalid_argument(
                    "remote framegraph gap capacity must be positive");
            }
            state = std::make_shared<FrameGraphDebuggerSnapshot>();
            state->revision = 1;
            state->source_kind = FrameGraphDebuggerSourceKind::Remote;
            state->source_label = "Remote / pending";
            state->connected = false;
            state->stale = true;
            state->status_detail = "waiting for remote target handshake";
            state->capture_info =
                "Remote topology connected; image capture is not enabled";
        }

        ~Impl()
        {
            disconnect_live();
        }

        std::shared_ptr<const FrameGraphDebuggerSnapshot> snapshot() const
        {
            std::lock_guard lock(mutex);
            return state;
        }

        bool send(Command command)
        {
            std::lock_guard lock(mutex);
            if (closed || !sender || !state->connected)
                return false;
            command.request_id = next_request_id++;
            if (!sender(command))
            {
                publish_error_locked("remote command queue is full");
                return false;
            }
            pending_commands.emplace(command.request_id, command.kind);
            if (command.kind == CommandKind::refresh_topology)
            {
                refresh_pending = true;
                needs_refresh = false;
                last_refresh_request = Clock::now();
            }
            return true;
        }

        bool refresh()
        {
            {
                std::lock_guard lock(mutex);
                if (closed || !sender || !state->connected || refresh_pending)
                {
                    return false;
                }
                const bool cadence_elapsed =
                    last_refresh_request == Clock::time_point{} ||
                    Clock::now() - last_refresh_request >=
                        std::chrono::milliseconds(500);
                if (!needs_refresh && !cadence_elapsed)
                    return false;
            }
            Command command;
            command.kind = CommandKind::refresh_topology;
            return send(std::move(command));
        }

        bool select_target(std::uint64_t target_id)
        {
            Command command;
            {
                std::lock_guard lock(mutex);
                if (pending_target_id == target_id)
                    return true;
                const auto found =
                    std::find_if(state->targets.begin(),
                                 state->targets.end(),
                                 [target_id](const auto& target)
                                 { return target.id == target_id; });
                if (found == state->targets.end())
                {
                    tc_log_error(
                        "remote framegraph source: unknown target id %llu",
                        static_cast<unsigned long long>(target_id));
                    return false;
                }
                command.kind = CommandKind::select_target;
                command.target_id = target_id;
                command.graph_revision = state->graph_revision;
            }
            if (!send(std::move(command)))
                return false;
            {
                std::lock_guard lock(mutex);
                pending_target_id = target_id;
            }
            return true;
        }

        bool select_pass(std::optional<std::uint64_t> pass_id)
        {
            std::lock_guard lock(mutex);
            auto next = std::make_shared<FrameGraphDebuggerSnapshot>(*state);
            const FrameGraphDebuggerPassSnapshot* selected = nullptr;
            if (pass_id)
            {
                const auto found =
                    std::find_if(next->passes.begin(),
                                 next->passes.end(),
                                 [pass_id](const auto& pass)
                                 { return pass.id == *pass_id; });
                if (found == next->passes.end())
                {
                    tc_log_error(
                        "remote framegraph source: unknown pass id %llu",
                        static_cast<unsigned long long>(*pass_id));
                    return false;
                }
                selected = &*found;
            }
            next->selected_pass_id = pass_id;
            next->symbols = selected ? selected->internal_symbols
                                     : std::vector<std::string>{};
            if (std::find(next->symbols.begin(),
                          next->symbols.end(),
                          next->selected_symbol) == next->symbols.end())
            {
                next->selected_symbol.clear();
            }
            next->pass_json = pass_summary(selected);
            publish_locked(std::move(next));
            return true;
        }

        template <typename Mutation> void mutate(Mutation mutation)
        {
            std::lock_guard lock(mutex);
            if (closed)
                return;
            auto next = std::make_shared<FrameGraphDebuggerSnapshot>(*state);
            mutation(*next);
            publish_locked(std::move(next));
        }

        bool ingest(const DecodedMessage& decoded)
        {
            std::lock_guard lock(mutex);
            const bool starts_session =
                std::holds_alternative<TargetHello>(decoded.message);
            if (decoded.envelope.session_id == 0 ||
                decoded.envelope.sequence == 0 ||
                (starts_session &&
                 decoded.envelope.session_id == active_session_id) ||
                (!starts_session &&
                 (decoded.envelope.session_id != active_session_id ||
                  decoded.envelope.sequence <= last_sequence)))
            {
                tc_log_error(
                    "remote framegraph source: invalid session or sequence");
                return false;
            }
            auto next = std::make_shared<FrameGraphDebuggerSnapshot>(*state);
            const bool changed =
                std::visit([&](const auto& message)
                           { return apply(*next, decoded, message); },
                           decoded.message);
            if (!changed)
                return false;
            active_session_id = decoded.envelope.session_id;
            last_sequence = decoded.envelope.sequence;
            publish_locked(std::move(next));
            return true;
        }

        bool connect_live(RemoteFrameGraphConnectionConfig config)
        {
            disconnect_live();
            {
                std::lock_guard lock(mutex);
                configured_client = config;
                closed = false;
            }
            auto next_client = std::make_unique<
                framegraph_remote_client::RemoteFrameGraphClient>(
                project_client_config(std::move(config)),
                [this](const DecodedMessage& message) { ingest(message); },
                [this](std::string detail)
                { disconnected(std::move(detail)); });
            auto* client_view = next_client.get();
            {
                std::lock_guard lock(mutex);
                client = std::move(next_client);
                sender = [client_view](const Command& command)
                { return client_view->send_command(command); };
                auto next =
                    std::make_shared<FrameGraphDebuggerSnapshot>(*state);
                next->status_detail = "connecting to remote target";
                next->stale = true;
                publish_locked(std::move(next));
            }
            if (client_view->start())
                return true;
            disconnect_live();
            disconnected("failed to start remote client");
            return false;
        }

        void connect_configured()
        {
            std::optional<RemoteFrameGraphConnectionConfig> config;
            {
                std::lock_guard lock(mutex);
                if (closed || client || !configured_client)
                    return;
                config = configured_client;
            }
            connect_live(std::move(*config));
        }

        void disconnect_live()
        {
            std::unique_ptr<framegraph_remote_client::RemoteFrameGraphClient>
                stopped;
            {
                std::lock_guard lock(mutex);
                sender = {};
                stopped = std::move(client);
            }
            if (stopped)
                stopped->stop();
        }

        void disconnected(std::string detail)
        {
            std::lock_guard lock(mutex);
            if (!state->connected && state->status_detail == detail)
                return;
            auto next = std::make_shared<FrameGraphDebuggerSnapshot>(*state);
            const bool was_connected = next->connected;
            next->connected = false;
            next->stale = true;
            next->state = FrameGraphDebuggerState::Unbound;
            next->status_detail = std::move(detail);
            if (was_connected)
            {
                append_gap(
                    *next,
                    FrameGraphDebuggerGapKind::Disconnect,
                    0,
                    "transport disconnected; retained topology is stale");
            }
            pending_commands.clear();
            pending_target_id.reset();
            refresh_pending = false;
            needs_refresh = true;
            publish_locked(std::move(next));
        }

        void close()
        {
            disconnect_live();
            {
                std::lock_guard lock(mutex);
                closed = true;
                configured_client.reset();
            }
            disconnected("remote source closed");
        }

    private:
        template <typename T>
        bool apply(FrameGraphDebuggerSnapshot&, const DecodedMessage&, const T&)
        {
            tc_log_error("remote framegraph source: unexpected message type "
                         "from target");
            return false;
        }

        bool apply(FrameGraphDebuggerSnapshot& next,
                   const DecodedMessage& decoded,
                   const TargetHello& hello)
        {
            pending_commands.clear();
            pending_target_id.reset();
            refresh_pending = false;
            needs_refresh = true;
            next = FrameGraphDebuggerSnapshot{};
            next.source_kind = FrameGraphDebuggerSourceKind::Remote;
            next.source_label =
                "Remote / " + hello.platform + " / " + hello.abi;
            next.session_id = decoded.envelope.session_id;
            next.connected = true;
            next.stale = true;
            next.state = FrameGraphDebuggerState::Bound;
            if ((hello.capabilities &
                 static_cast<std::uint64_t>(Capability::topology)) == 0)
            {
                next.state = FrameGraphDebuggerState::Error;
                next.status_detail =
                    "remote target does not advertise topology capability";
                tc_log_error("remote framegraph source: %s",
                             next.status_detail.c_str());
            }
            else
            {
                next.status_detail =
                    "remote target connected; waiting for topology";
            }
            next.capture_info =
                "Remote topology connected; image capture is not enabled";
            return true;
        }

        bool apply(FrameGraphDebuggerSnapshot& next,
                   const DecodedMessage&,
                   const TopologySnapshot& topology)
        {
            if (next.graph_revision != 0 &&
                topology.graph_revision < next.graph_revision)
            {
                tc_log_error(
                    "remote framegraph source: topology revision regressed "
                    "from %llu to %llu",
                    static_cast<unsigned long long>(next.graph_revision),
                    static_cast<unsigned long long>(topology.graph_revision));
                return false;
            }
            pending_target_id.reset();
            next.graph_revision = topology.graph_revision;
            next.targets.clear();
            next.targets.reserve(topology.targets.size());
            for (const auto& target : topology.targets)
            {
                next.targets.push_back(
                    {target.id, target.label, target.renderable});
            }
            next.selected_target_id =
                topology.selected_target_id == 0
                    ? std::optional<std::uint64_t>{}
                    : std::optional<std::uint64_t>{topology.selected_target_id};
            next.passes.clear();
            next.passes.reserve(topology.passes.size());
            for (const auto& pass : topology.passes)
            {
                next.passes.push_back({pass.id,
                                       pass.authored_index,
                                       pass.name,
                                       pass.type,
                                       pass.enabled,
                                       pass.passthrough,
                                       pass.reads,
                                       pass.writes,
                                       pass.internal_symbols});
            }
            const auto selected_pass =
                std::find_if(next.passes.begin(),
                             next.passes.end(),
                             [&](const auto& pass)
                             { return next.selected_pass_id == pass.id; });
            if (selected_pass == next.passes.end())
            {
                next.selected_pass_id.reset();
                next.symbols.clear();
                next.selected_symbol.clear();
                next.pass_json.clear();
            }
            else
            {
                next.symbols = selected_pass->internal_symbols;
                next.pass_json = pass_summary(&*selected_pass);
            }
            next.resources = topology.resources;
            if (std::find(next.resources.begin(),
                          next.resources.end(),
                          next.selected_resource) == next.resources.end())
            {
                next.selected_resource.clear();
            }
            next.render_stats = topology.render_stats;
            next.pipeline_info = topology_summary(topology);
            next.connected = true;
            next.stale = false;
            next.state = FrameGraphDebuggerState::Bound;
            next.status_detail = "remote topology updated";
            return true;
        }

        bool apply(FrameGraphDebuggerSnapshot& next,
                   const DecodedMessage&,
                   const Status& status)
        {
            next.graph_revision = status.graph_revision;
            next.state = project_state(status.state);
            next.status_detail = status.detail;
            next.timing =
                "Target time: " + std::to_string(status.target_time_ns) +
                " ns; remote queue: " + std::to_string(status.queue_depth);
            next.dropped_messages =
                std::max(next.dropped_messages, status.dropped_captures);
            const auto pending = pending_commands.find(status.request_id);
            if (pending != pending_commands.end())
            {
                if (pending->second == CommandKind::select_target)
                    pending_target_id.reset();
                if (pending->second == CommandKind::refresh_topology)
                {
                    refresh_pending = false;
                }
                pending_commands.erase(pending);
            }
            if (status.code == StatusCode::stale_revision)
            {
                needs_refresh = true;
                next.stale = true;
                next.status_detail =
                    "remote topology revision is stale; refreshing";
            }
            return true;
        }

        bool apply(FrameGraphDebuggerSnapshot& next,
                   const DecodedMessage&,
                   const DropEvent& drop)
        {
            next.dropped_messages += drop.dropped_items;
            append_gap(next,
                       FrameGraphDebuggerGapKind::TransportDrop,
                       drop.dropped_items,
                       "remote " +
                           std::to_string(static_cast<unsigned>(drop.kind)) +
                           " queue drop");
            next.status_detail = "remote transport reported dropped messages";
            return true;
        }

        bool apply(FrameGraphDebuggerSnapshot& next,
                   const DecodedMessage&,
                   const ErrorEvent& error)
        {
            next.status_detail = "target error " + std::to_string(error.code) +
                                 ": " + error.detail;
            next.state = FrameGraphDebuggerState::Error;
            tc_log_error("remote framegraph source: target error %u: %s",
                         error.code,
                         error.detail.c_str());
            const auto pending =
                pending_commands.find(error.related_request_id);
            if (pending != pending_commands.end())
            {
                if (pending->second == CommandKind::select_target)
                    pending_target_id.reset();
                if (pending->second == CommandKind::refresh_topology)
                {
                    refresh_pending = false;
                }
                pending_commands.erase(pending);
            }
            return true;
        }

        void append_gap(FrameGraphDebuggerSnapshot& next,
                        FrameGraphDebuggerGapKind kind,
                        std::uint64_t count,
                        std::string detail)
        {
            if (next.gaps.size() == gap_capacity)
            {
                next.gaps.erase(next.gaps.begin());
            }
            next.gaps.push_back({kind, count, std::move(detail)});
        }

        void publish_error_locked(std::string detail)
        {
            auto next = std::make_shared<FrameGraphDebuggerSnapshot>(*state);
            next->status_detail = std::move(detail);
            next->state = FrameGraphDebuggerState::Error;
            publish_locked(std::move(next));
        }

        void publish_locked(std::shared_ptr<FrameGraphDebuggerSnapshot> next)
        {
            next->revision = state->revision + 1;
            state = std::move(next);
        }

        std::size_t gap_capacity = 0;
        CommandSender sender;
        mutable std::mutex mutex;
        std::shared_ptr<FrameGraphDebuggerSnapshot> state;
        std::unordered_map<std::uint64_t, CommandKind> pending_commands;
        std::optional<std::uint64_t> pending_target_id;
        std::uint64_t next_request_id = 1;
        std::uint64_t active_session_id = 0;
        std::uint64_t last_sequence = 0;
        bool refresh_pending = false;
        bool needs_refresh = true;
        bool closed = false;
        Clock::time_point last_refresh_request{};
        std::optional<RemoteFrameGraphConnectionConfig> configured_client;
        std::unique_ptr<framegraph_remote_client::RemoteFrameGraphClient>
            client;
    };

    RemoteFrameGraphDebuggerSource::RemoteFrameGraphDebuggerSource(
        std::size_t gap_capacity, CommandSender sender)
        : impl_(std::make_unique<Impl>(gap_capacity, std::move(sender)))
    {
    }

    RemoteFrameGraphDebuggerSource::~RemoteFrameGraphDebuggerSource() = default;

    std::shared_ptr<const FrameGraphDebuggerSnapshot>
    RemoteFrameGraphDebuggerSource::snapshot() const
    {
        return impl_->snapshot();
    }

    bool RemoteFrameGraphDebuggerSource::refresh()
    {
        return impl_->refresh();
    }

    void RemoteFrameGraphDebuggerSource::finish_frame() {}

    void RemoteFrameGraphDebuggerSource::connect()
    {
        impl_->connect_configured();
    }

    void RemoteFrameGraphDebuggerSource::disconnect()
    {
        impl_->disconnect_live();
        impl_->disconnected("remote source disconnected");
    }

    void RemoteFrameGraphDebuggerSource::close()
    {
        impl_->close();
    }

    bool RemoteFrameGraphDebuggerSource::select_target(std::uint64_t target_id)
    {
        return impl_->select_target(target_id);
    }

    bool RemoteFrameGraphDebuggerSource::select_pass(
        std::optional<std::uint64_t> pass_id)
    {
        return impl_->select_pass(pass_id);
    }

    void RemoteFrameGraphDebuggerSource::set_mode(FrameGraphDebuggerMode mode)
    {
        impl_->mutate([mode](auto& next) { next.mode = mode; });
    }

    void RemoteFrameGraphDebuggerSource::set_selected_symbol(
        const std::string& symbol)
    {
        impl_->mutate([&symbol](auto& next) { next.selected_symbol = symbol; });
    }

    void RemoteFrameGraphDebuggerSource::set_selected_resource(
        const std::string& resource)
    {
        impl_->mutate([&resource](auto& next)
                      { next.selected_resource = resource; });
    }

    void RemoteFrameGraphDebuggerSource::set_channel_mode(int mode)
    {
        impl_->mutate([mode](auto& next) { next.channel_mode = mode; });
    }

    void RemoteFrameGraphDebuggerSource::set_paused(bool paused)
    {
        impl_->mutate([paused](auto& next) { next.paused = paused; });
    }

    void RemoteFrameGraphDebuggerSource::set_highlight_hdr(bool enabled)
    {
        impl_->mutate([enabled](auto& next) { next.highlight_hdr = enabled; });
    }

    std::string RemoteFrameGraphDebuggerSource::analyze_hdr()
    {
        return "HDR analysis requires a remote image capture";
    }

    bool
    RemoteFrameGraphDebuggerSource::render_image(tgfx::RenderContext2&,
                                                 tgfx::TextureHandle,
                                                 FrameGraphDebuggerImageKind,
                                                 std::uint32_t,
                                                 std::uint32_t,
                                                 int,
                                                 bool)
    {
        return false;
    }

    std::vector<std::uint8_t>
    RemoteFrameGraphDebuggerSource::read_depth_normalized(tgfx::IRenderDevice&,
                                                          int* width,
                                                          int* height)
    {
        if (width)
            *width = 0;
        if (height)
            *height = 0;
        return {};
    }

    bool RemoteFrameGraphDebuggerSource::ingest(const DecodedMessage& message)
    {
        return impl_->ingest(message);
    }

    bool RemoteFrameGraphDebuggerSource::connect(
        RemoteFrameGraphConnectionConfig config)
    {
        return impl_->connect_live(std::move(config));
    }

    void
    RemoteFrameGraphDebuggerSource::transport_disconnected(std::string detail)
    {
        impl_->disconnected(std::move(detail));
    }

} // namespace termin
