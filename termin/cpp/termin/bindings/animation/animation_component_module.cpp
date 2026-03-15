#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/vector.h>

#include "termin/animation/animation_player.hpp"
#include "termin/animation/tc_animation_handle.hpp"
#include "termin/render/skeleton_controller.hpp"
#include "termin/bindings/entity/entity_helpers.hpp"

namespace nb = nanobind;
using namespace termin;
using namespace termin::animation;

namespace {

void bind_animation_player(nb::module_& m) {
    nb::class_<AnimationPlayer, Component>(m, "AnimationPlayer")
        .def("__init__", [](nb::handle self) {
            termin::cxx_component_init<AnimationPlayer>(self);
        })
        .def_rw("clips", &AnimationPlayer::clips)
        .def_rw("_current_clip_name", &AnimationPlayer::_current_clip_name)
        .def_rw("time", &AnimationPlayer::time)
        .def_rw("playing", &AnimationPlayer::playing)
        .def_prop_ro("current", [](AnimationPlayer& self) {
            return self.current();
        }, nb::rv_policy::reference)
        .def_prop_ro("clips_map", [](AnimationPlayer& self) {
            nb::dict d;
            for (const auto& [name, idx] : self.clips_map()) {
                d[nb::str(name.c_str())] = idx;
            }
            return d;
        })
        .def("set_current", &AnimationPlayer::set_current)
        .def("play", &AnimationPlayer::play, nb::arg("name"), nb::arg("restart") = true)
        .def("stop", &AnimationPlayer::stop)
        .def("update_bones_at_time", &AnimationPlayer::update_bones_at_time)
        .def_prop_ro("target_skeleton",
            &AnimationPlayer::target_skeleton,
            nb::rv_policy::reference)
        .def_prop_rw("target_skeleton_controller",
            &AnimationPlayer::target_skeleton_controller,
            &AnimationPlayer::set_target_skeleton_controller,
            nb::rv_policy::reference)
        .def("add_clip", [](AnimationPlayer& self, const TcAnimationClip& clip) {
            self.clips.push_back(clip);
        }, nb::arg("clip"));
}

} // namespace

NB_MODULE(_components_animation_native, m) {
    m.doc() = "Native C++ animation component module (AnimationPlayer)";

    nb::module_::import_("termin.entity._entity_native");
    nb::module_::import_("termin.skeleton._skeleton_native");
    nb::module_::import_("termin.skeleton._components_skeleton_native");
    nb::module_::import_("termin.visualization.animation._animation_native");

    bind_animation_player(m);
}
