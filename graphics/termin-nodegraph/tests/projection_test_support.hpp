#pragma once

#include <cassert>
#include <cmath>
#include <string>
#include <utility>

#include <termin/nodegraph/projection.hpp>

namespace termin::nodegraph::test {

    constexpr float title_height = 26.0f;
    constexpr float socket_row_height = 20.0f;

    inline bool near(float lhs, float rhs, float tolerance = 1.0e-4f) {
        return std::abs(lhs - rhs) <= tolerance;
    }

    inline bool same_item(tc_graphic_item_handle lhs, tc_graphic_item_handle rhs) {
        return lhs.scene_id == rhs.scene_id && lhs.index == rhs.index && lhs.generation == rhs.generation;
    }

    inline bool valid_item(tc_graphic_item_handle item) {
        return !tc_graphic_item_handle_is_invalid(item);
    }

    inline NodeDescriptor node(
        std::string id, std::string kind, float x, float y, std::string input_type = {}, std::string output_type = {}) {
        NodeDescriptor result;
        result.id = std::move(id);
        result.kind = std::move(kind);
        result.title = result.id;
        result.x = x;
        result.y = y;
        result.width = 190.0f;
        result.height = 120.0f;
        if (!input_type.empty()) {
            result.inputs.push_back({"in", std::move(input_type), false});
        }
        if (!output_type.empty()) {
            result.outputs.push_back({"out", std::move(output_type), true});
        }
        return result;
    }

    inline ConnectRequest connect(NodeHandle source, NodeHandle destination, std::string id) {
        return {source, "out", destination, "in", std::move(id)};
    }

    inline SocketRef input(NodeHandle node_handle) {
        return {node_handle, "in", SocketDirection::Input};
    }

    inline SocketRef output(NodeHandle node_handle) {
        return {node_handle, "out", SocketDirection::Output};
    }

    inline std::pair<float, float> socket_position(const Node& value, SocketDirection direction, std::size_t row = 0) {
        return {
            value.x + (direction == SocketDirection::Output ? value.width : 0.0f),
            value.y + title_height + socket_row_height * (static_cast<float>(row) + 0.5f),
        };
    }

    inline bool pointer(NodeGraphProjection& projection,
                        PointerPhase phase,
                        float x,
                        float y,
                        float zoom = 1.0f,
                        PointerButton button = PointerButton::Left) {
        return projection.pointer({phase, button, x, y, zoom});
    }

    inline void click(NodeGraphProjection& projection, float x, float y, float zoom = 1.0f) {
        assert(pointer(projection, PointerPhase::Down, x, y, zoom));
        pointer(projection, PointerPhase::Up, x, y, zoom);
    }

} // namespace termin::nodegraph::test
