#include <termin/nodegraph/projection.hpp>

#include <algorithm>

namespace termin::nodegraph {

    namespace {

        ParameterEditorKind inferred_kind(tc::trent_view value) {
            if (value.is_bool())
                return ParameterEditorKind::Boolean;
            if (value.is_integer())
                return ParameterEditorKind::Integer;
            if (value.is_numer())
                return ParameterEditorKind::FloatingPoint;
            return ParameterEditorKind::Text;
        }

        ParameterEditorKind named_kind(tc::trent_view value, ParameterEditorKind fallback) {
            const std::string name = value.as_string();
            if (name == "bool" || name == "boolean")
                return ParameterEditorKind::Boolean;
            if (name == "enum" || name == "enumeration")
                return ParameterEditorKind::Enumeration;
            if (name == "int" || name == "integer")
                return ParameterEditorKind::Integer;
            if (name == "float" || name == "double" || name == "number")
                return ParameterEditorKind::FloatingPoint;
            if (name == "string" || name == "text")
                return ParameterEditorKind::Text;
            return fallback;
        }

    } // namespace

    std::vector<ParameterEditorDescriptor> PresentationPolicy::parameter_editors(const Node& node) const {
        std::vector<ParameterEditorDescriptor> result;
        const tc::trent_view specs = node.data.view().get("param_specs");
        for (const tc::trent_dict_entry_view entry : node.params.view().as_dict()) {
            if (entry.key == nullptr || entry.value == nullptr)
                continue;
            const tc::trent_view value(entry.value);
            const tc::trent_view spec = specs.get(entry.key);
            ParameterEditorDescriptor descriptor;
            descriptor.name = entry.key;
            descriptor.label = spec.get("label").as_string(descriptor.name);
            descriptor.kind = named_kind(spec.get("kind"), inferred_kind(value));
            descriptor.minimum = spec.get("min").as_numer(descriptor.minimum);
            descriptor.maximum = spec.get("max").as_numer(descriptor.maximum);
            descriptor.step =
                spec.get("step").as_numer(descriptor.kind == ParameterEditorKind::Integer ? 1.0 : descriptor.step);
            descriptor.decimals = static_cast<int>(spec.get("decimals").as_integer(descriptor.decimals));
            for (const tc::trent_view choice : spec.get("items").as_list()) {
                if (choice.is_dict()) {
                    ParameterChoice item;
                    item.value = choice.get("value").as_string();
                    item.label = choice.get("label").as_string(item.value);
                    descriptor.choices.push_back(std::move(item));
                } else {
                    const std::string item = choice.as_string();
                    descriptor.choices.push_back({item, item});
                }
            }
            result.push_back(std::move(descriptor));
        }
        return result;
    }

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
