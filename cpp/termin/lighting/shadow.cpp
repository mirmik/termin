#include "termin/lighting/shadow.hpp"
#include "termin/render/handles.hpp"

namespace termin {

GPUTextureHandle* ShadowMapArrayEntry::texture() const {
    if (!fbo) {
        return nullptr;
    }
    return fbo->color_texture();
}

} // namespace termin
