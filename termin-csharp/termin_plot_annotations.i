// Shared value-only annotation surface for full and plot-d3d11 profiles.
// Included while the surrounding interface is inside namespace tcplot.

struct PlotAnnotationHandle {
    unsigned long long layer_id;
    unsigned int index;
    unsigned int generation;

    PlotAnnotationHandle();
    bool valid() const;
};

struct PlotDataMarkerBindingSnapshot2D {
    bool available;
    PlotAnnotationHandle annotation;
    double x;
    double y;
    std::string text;
    bool hovered;
    bool dragging;

    PlotDataMarkerBindingSnapshot2D();
};

struct PlotAnnotationActionPoll2D {
    bool available;
    PlotAnnotationHandle annotation;
    std::string action;

    PlotAnnotationActionPoll2D();
};

%extend PlotView2D {
    tcplot::PlotAnnotationHandle create_data_marker(
        double x, double y, const char* text) {
        return $self->create_data_marker(x, y, text);
    }

    bool update_data_marker(
        tcplot::PlotAnnotationHandle handle,
        double x,
        double y,
        const char* text) {
        return $self->update_data_marker(handle, x, y, text);
    }

    tcplot::PlotDataMarkerBindingSnapshot2D data_marker_snapshot(
        tcplot::PlotAnnotationHandle handle) {
        return $self->data_marker_binding_snapshot(handle);
    }

    bool destroy_annotation(tcplot::PlotAnnotationHandle handle) {
        return $self->destroy_annotation(handle);
    }

    tcplot::PlotAnnotationActionPoll2D take_annotation_action() {
        return $self->take_annotation_action();
    }
}
