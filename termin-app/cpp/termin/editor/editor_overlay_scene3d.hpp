#pragma once

#include <cstdint>

#include <termin/geom/affine3.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/geom/ray3.hpp>
#include <termin_visual_scene/interaction3d.hpp>
#include <termin_visual_scene/paint3d.hpp>

namespace tgfx {
    class RenderContext2;
}

namespace termin {
    class ImmediateRenderer;

    inline constexpr char EditorOverlayDrawProtocol3D[] = "termin.editor.overlay-drawable.v1";

    struct EditorOverlayDrawContext3D {
        ImmediateRenderer* renderer = nullptr;
        tgfx::RenderContext2* render_context = nullptr;
        Mat44f view{};
        Mat44f projection{};
        Affine3d world_from_local = Affine3d::identity();
        visual::VisualItem3DHandle item = tc_visual_item3d_handle_invalid();
    };

    // Renderer-specific behavior is supplied through a protocol packet. The
    // overlay host knows VisualScene3D and this protocol only, never concrete
    // visual item types.
    class EditorOverlayDrawable3D {
    public:
        virtual ~EditorOverlayDrawable3D() = default;
        virtual bool draw(const EditorOverlayDrawContext3D& context) const = 0;
    };

    struct EditorOverlayDrawPacket3D {
        const EditorOverlayDrawable3D* drawable = nullptr;
    };

    class EditorOverlayScene3D {
    public:
        EditorOverlayScene3D();
        ~EditorOverlayScene3D();

        EditorOverlayScene3D(const EditorOverlayScene3D&) = delete;
        EditorOverlayScene3D& operator=(const EditorOverlayScene3D&) = delete;

        visual::TcVisualScene3D& scene() noexcept {
            return _scene;
        }
        const visual::TcVisualScene3D& scene() const noexcept {
            return _scene;
        }
        visual::SceneInteraction3D& interaction() noexcept {
            return _interaction;
        }
        const visual::SceneInteraction3D& interaction() const noexcept {
            return _interaction;
        }

        bool route_pointer(visual::PointerEventKind3D kind,
                           Ray3 world_ray,
                           std::uint32_t button = 0,
                           visual::PointerId3D pointer = 1);
        bool paint(ImmediateRenderer* renderer,
                   tgfx::RenderContext2* render_context,
                   const Mat44f& view,
                   const Mat44f& projection,
                   std::uint32_t viewport_width,
                   std::uint32_t viewport_height) const;

        // Sends final Leave/Cancel callbacks before destroying adopted items.
        void clear();

    private:
        tc_visual_scene3d_handle _handle = tc_visual_scene3d_handle_invalid();
        visual::TcVisualScene3D _scene;
        visual::SceneInteraction3D _interaction;
    };

} // namespace termin
