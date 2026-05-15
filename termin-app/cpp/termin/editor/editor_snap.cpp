#include "termin/editor/editor_snap.hpp"

namespace termin {

EditorSnapRegistry& EditorSnapRegistry::instance() {
    static EditorSnapRegistry registry;
    return registry;
}

void EditorSnapRegistry::register_provider(std::unique_ptr<EditorSnapProvider> provider) {
    if (provider) {
        _providers.push_back(std::move(provider));
    }
}

bool EditorSnapRegistry::snap(const EditorSnapRequest& request, EditorSnapResult& result) {
    if (request.source == EditorSnapSource::None) {
        return false;
    }

    if (request.source == EditorSnapSource::VisibleGeometry) {
        result.success = true;
        result.position = request.reference_position;
        return true;
    }

    for (const auto& provider : _providers) {
        if (provider->snap(request, result) && result.success) {
            return true;
        }
    }
    return false;
}

} // namespace termin
