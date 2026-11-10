#include <algorithm>
#include <atomic>
#include <chrono>
#include <cassert>
#include <cstdio>
#include <exception>
#include <stdexcept>
#include <thread>

#include <SDL2/SDL.h>

#include "termin/platform/sdl_backend_window.hpp"
#include "termin/window/window_manager.hpp"
#include "tgfx2/graphics_host.hpp"

int main() {
    try {
        auto session = termin::create_native_windowed_graphics();
        termin::WindowManager windows(*session);

        const termin::WindowHandle first = windows.create_window({"manager first", 320, 200});
        const termin::WindowHandle second = windows.create_window({"manager second", 240, 160});
        assert(first && second && first != second);
        assert(windows.size() == 2);
        assert(&windows.window(first).graphics_host() == &session->graphics());
        assert(&windows.window(second).graphics_host() == &session->graphics());

        windows.pump_events();
        windows.take_events(first);
        windows.take_events(second);

        auto& second_sdl = static_cast<termin::SDLBackendWindow&>(windows.window(second));

        SDL_Event key{};
        key.type = SDL_KEYDOWN;
        key.key.type = SDL_KEYDOWN;
        key.key.windowID = SDL_GetWindowID(second_sdl.sdl_window());
        key.key.keysym.sym = SDLK_c;
        key.key.keysym.scancode = SDL_SCANCODE_C;
        assert(SDL_PushEvent(&key) == 1);
        // Waiting removes the first event from SDL; it must still be routed to
        // the secondary window and survive the normal portable queue transfer.
        windows.wait_events(0.0);

        // Native focus, resize and pointer events can arrive after the initial
        // drain. Check queue accounting independently of that ambient traffic.
        const auto first_pump_count = windows.pump_events();
        assert(first_pump_count >= 1);
        assert(windows.pending_event_count(first) + windows.pending_event_count(second) == first_pump_count);
        const auto first_pending = windows.pending_event_count(first);
        const auto second_pending = windows.pending_event_count(second);
        assert(windows.has_pending_events());
        const auto before_pending_wait = std::chrono::steady_clock::now();
        windows.wait_events(2.0);
        assert(std::chrono::steady_clock::now() - before_pending_wait < std::chrono::seconds(1));
        const auto second_pump_count = windows.pump_events();
        assert(windows.pending_event_count(first) >= first_pending);
        assert(windows.pending_event_count(second) >= second_pending);
        assert(windows.pending_event_count(first) + windows.pending_event_count(second)
            == first_pump_count + second_pump_count);

        const auto first_events = windows.take_events(first);
        const auto second_events = windows.take_events(second);
        assert(first_events.size() + second_events.size() == first_pump_count + second_pump_count);
        assert(windows.pending_event_count(first) == 0);
        assert(windows.pending_event_count(second) == 0);
        const auto is_key_pressed = [](const termin::WindowEvent& event) {
            return event.type == termin::WindowEventType::KeyPressed;
        };
        assert(std::ranges::count_if(first_events, is_key_pressed) == 0);
        assert(std::ranges::count_if(second_events, is_key_pressed) == 1);
        const auto received_key = std::ranges::find_if(second_events, is_key_pressed);
        assert(received_key->key.key == termin::WindowKey::C);

        // Hide/show is deterministic even on SDL offscreen and bare Xvfb,
        // whereas minimize/restore needs a real window manager. Together with
        // the adapter's zero-size test this covers unavailable presentation;
        // physical minimize/restore remains a platform smoke scenario.
        const auto presentation_changed = [](const termin::WindowEvent& event) {
            return event.type == termin::WindowEventType::PresentationChanged;
        };
        assert(second_sdl.presentable());
        SDL_HideWindow(second_sdl.sdl_window());
        assert(!second_sdl.presentable());
        windows.wait_events(0.0);
        windows.pump_events();
        const auto hidden_events = windows.take_events(second);
        assert(std::ranges::any_of(hidden_events, presentation_changed));
        windows.take_events(first);

        SDL_ShowWindow(second_sdl.sdl_window());
        windows.wait_events(0.0);
        windows.pump_events();
        const auto shown_events = windows.take_events(second);
        assert(std::ranges::any_of(shown_events, presentation_changed));
        assert(second_sdl.presentable());
        windows.take_events(first);

        bool session_close_rejected = false;
        try {
            session->close();
        } catch (const std::logic_error&) {
            session_close_rejected = true;
        }
        assert(session_close_rejected);
        assert(!session->graphics().is_closed());

        windows.destroy_window(first);
        assert(!windows.contains(first));
        assert(windows.size() == 1);
        bool stale_rejected = false;
        try {
            (void)windows.window(first);
        } catch (const std::invalid_argument&) {
            stale_rejected = true;
        }
        assert(stale_rejected);
        assert(&windows.window(second).graphics_host() == &session->graphics());

        const termin::WindowHandle replacement = windows.create_window({"manager replacement", 200, 120});
        assert(replacement.slot == first.slot);
        assert(replacement.generation != first.generation);
        const auto handles = windows.handles();
        assert(handles.size() == 2);
        assert(handles.front() == second);
        assert(handles.back() == replacement);

        SDL_Event quit{};
        quit.type = SDL_QUIT;
        assert(SDL_PushEvent(&quit) == 1);
        const auto quit_pump_count = windows.pump_events();
        assert(quit_pump_count >= 2);
        size_t taken_count = 0;
        for (termin::WindowHandle handle : windows.handles()) {
            const auto events = windows.take_events(handle);
            taken_count += events.size();
            assert(std::ranges::count_if(events, [](const termin::WindowEvent& event) {
                return event.type == termin::WindowEventType::CloseRequested;
            }) == 1);
            assert(windows.pending_event_count(handle) == 0);
        }
        assert(taken_count == quit_pump_count);

        windows.close();
        assert(!windows.is_open());
        const auto wake = session->wake_handle();
        SDL_FlushEvents(SDL_FIRSTEVENT, SDL_LASTEVENT);
        wake->wake();
        // Notification posted between work inspection and wait is durable.
        session->wait_events();
        SDL_FlushEvents(SDL_FIRSTEVENT, SDL_LASTEVENT);
        const auto before_deadline = std::chrono::steady_clock::now();
        session->wait_events(0.02);
        assert(std::chrono::steady_clock::now() - before_deadline >= std::chrono::milliseconds(15));
        std::atomic<bool> published{false};
        std::thread producer([&] {
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
            published.store(true);
            wake->wake();
        });
        size_t wake_iterations = 0;
        while (!published.load()) {
            session->wait_events(1.0);
            ++wake_iterations;
        }
        producer.join();
        assert(wake_iterations <= 2);
        // Exercise check-to-wait races repeatedly, including coalesced wakes.
        for (int attempt = 0; attempt < 50; ++attempt) {
            published.store(false);
            std::thread concurrent([&] { published.store(true); wake->wake(); wake->wake(); });
            while (!published.load())
                session->wait_events(1.0);
            concurrent.join();
        }
        session->close();
        wake->wake(); // stale producer handle is harmless after owner teardown
        return 0;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "WindowManager live test skipped: %s\n", error.what());
        return 77;
    }
}
