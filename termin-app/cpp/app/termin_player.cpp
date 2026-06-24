#include "termin/player/player_runtime_host.hpp"

int main(int argc, char* argv[]) {
    termin::player::PlayerRuntimeHost host;
    return host.run(argc, argv);
}

