// Borrowed GraphicsHost access for language-neutral retained document hosting.
// The managed owner must retain GpuHost until all document renderers are closed.
%extend tcplot::GpuHost {
    unsigned long long native_graphics_host() {
        return reinterpret_cast<unsigned long long>(&$self->graphics());
    }
}
