#include <termin/nodegraph/projection.hpp>

#include <algorithm>

namespace termin::nodegraph {

    NodePalette DefaultPresentationPolicy::node_palette(const Node&) const {
        return {
            .body = {0.17f, 0.20f, 0.27f, 1.0f},
            .title = {0.24f, 0.28f, 0.38f, 1.0f},
            .border = {0.32f, 0.36f, 0.48f, 1.0f},
            .text = {0.92f, 0.94f, 0.98f, 1.0f},
        };
    }

    ProjectionColor DefaultPresentationPolicy::socket_color(const Node&, const Socket&, SocketDirection) const {
        return {0.68f, 0.68f, 0.70f, 1.0f};
    }

} // namespace termin::nodegraph
