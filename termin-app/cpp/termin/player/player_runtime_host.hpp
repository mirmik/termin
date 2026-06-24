#pragma once

#include <filesystem>

namespace termin::player {

class PlayerRuntimeHost {
public:
    struct Impl;

    PlayerRuntimeHost();
    ~PlayerRuntimeHost();

    PlayerRuntimeHost(const PlayerRuntimeHost&) = delete;
    PlayerRuntimeHost& operator=(const PlayerRuntimeHost&) = delete;

    int run(int argc, char** argv);
    void request_quit(int exit_code);

private:
    Impl* impl_ = nullptr;
};

} // namespace termin::player
