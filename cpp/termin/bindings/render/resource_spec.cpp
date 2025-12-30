#include "common.hpp"
#include <nanobind/stl/optional.h>
#include "termin/render/resource_spec.hpp"

namespace termin {

void bind_resource_spec(nb::module_& m) {
    nb::class_<ResourceSpec>(m, "ResourceSpec")
        .def(nb::init<>())
        .def(nb::init<std::string, std::string>(),
             nb::arg("resource"),
             nb::arg("resource_type") = "fbo")
        // Full constructor
        .def("__init__", [](ResourceSpec* self,
            const std::string& resource,
            const std::string& resource_type,
            nb::object size,
            nb::object clear_color,
            nb::object clear_depth,
            nb::object format,
            int samples
        ) {
            new (self) ResourceSpec();
            self->resource = resource;
            self->resource_type = resource_type;
            self->samples = samples;

            if (!size.is_none()) {
                nb::tuple t = nb::cast<nb::tuple>(size);
                self->size = std::make_pair(nb::cast<int>(t[0]), nb::cast<int>(t[1]));
            }
            if (!clear_color.is_none()) {
                nb::tuple t = nb::cast<nb::tuple>(clear_color);
                self->clear_color = std::array<double, 4>{
                    nb::cast<double>(t[0]), nb::cast<double>(t[1]),
                    nb::cast<double>(t[2]), nb::cast<double>(t[3])
                };
            }
            if (!clear_depth.is_none()) {
                self->clear_depth = nb::cast<float>(clear_depth);
            }
            if (!format.is_none()) {
                self->format = nb::cast<std::string>(format);
            }
        },
            nb::arg("resource"),
            nb::arg("resource_type") = "fbo",
            nb::arg("size") = nb::none(),
            nb::arg("clear_color") = nb::none(),
            nb::arg("clear_depth") = nb::none(),
            nb::arg("format") = nb::none(),
            nb::arg("samples") = 1
        )
        .def_rw("resource", &ResourceSpec::resource)
        .def_rw("resource_type", &ResourceSpec::resource_type)
        .def_rw("samples", &ResourceSpec::samples)
        // size property: optional<pair<int,int>> <-> tuple or None
        .def_prop_rw("size",
            [](const ResourceSpec& self) -> nb::object {
                if (self.size) {
                    return nb::make_tuple(self.size->first, self.size->second);
                }
                return nb::none();
            },
            [](ResourceSpec& self, nb::object val) {
                if (val.is_none()) {
                    self.size = std::nullopt;
                } else {
                    nb::tuple t = nb::cast<nb::tuple>(val);
                    self.size = std::make_pair(nb::cast<int>(t[0]), nb::cast<int>(t[1]));
                }
            }
        )
        // clear_color property: optional<array<float,4>> <-> tuple or None
        .def_prop_rw("clear_color",
            [](const ResourceSpec& self) -> nb::object {
                if (self.clear_color) {
                    auto& c = *self.clear_color;
                    return nb::make_tuple(c[0], c[1], c[2], c[3]);
                }
                return nb::none();
            },
            [](ResourceSpec& self, nb::object val) {
                if (val.is_none()) {
                    self.clear_color = std::nullopt;
                } else {
                    nb::tuple t = nb::cast<nb::tuple>(val);
                    self.clear_color = std::array<double, 4>{
                        nb::cast<double>(t[0]), nb::cast<double>(t[1]),
                        nb::cast<double>(t[2]), nb::cast<double>(t[3])
                    };
                }
            }
        )
        // clear_depth property: optional<float> <-> float or None
        .def_prop_rw("clear_depth",
            [](const ResourceSpec& self) -> nb::object {
                if (self.clear_depth) {
                    return nb::cast(*self.clear_depth);
                }
                return nb::none();
            },
            [](ResourceSpec& self, nb::object val) {
                if (val.is_none()) {
                    self.clear_depth = std::nullopt;
                } else {
                    self.clear_depth = nb::cast<float>(val);
                }
            }
        )
        // format property: optional<string> <-> str or None
        .def_prop_rw("format",
            [](const ResourceSpec& self) -> nb::object {
                if (self.format) {
                    return nb::cast(*self.format);
                }
                return nb::none();
            },
            [](ResourceSpec& self, nb::object val) {
                if (val.is_none()) {
                    self.format = std::nullopt;
                } else {
                    self.format = nb::cast<std::string>(val);
                }
            }
        )
        // serialize() method - returns lists for JSON compatibility
        .def("serialize", [](const ResourceSpec& self) -> nb::dict {
            nb::dict data;
            data["resource"] = self.resource;
            data["resource_type"] = self.resource_type;
            if (self.size) {
                nb::list size_list;
                size_list.append(self.size->first);
                size_list.append(self.size->second);
                data["size"] = size_list;
            }
            if (self.clear_color) {
                auto& c = *self.clear_color;
                nb::list color_list;
                color_list.append(c[0]);
                color_list.append(c[1]);
                color_list.append(c[2]);
                color_list.append(c[3]);
                data["clear_color"] = color_list;
            }
            if (self.clear_depth) {
                data["clear_depth"] = *self.clear_depth;
            }
            if (self.format) {
                data["format"] = *self.format;
            }
            if (self.samples != 1) {
                data["samples"] = self.samples;
            }
            return data;
        })
        // deserialize() classmethod - handles both list and tuple
        .def_static("deserialize", [](nb::dict data) -> ResourceSpec {
            ResourceSpec spec;
            spec.resource = data.contains("resource") ?
                nb::cast<std::string>(data["resource"]) : "";
            spec.resource_type = data.contains("resource_type") ?
                nb::cast<std::string>(data["resource_type"]) : "fbo";
            spec.samples = data.contains("samples") ?
                nb::cast<int>(data["samples"]) : 1;

            if (data.contains("size")) {
                nb::object size_obj = data["size"];
                spec.size = std::make_pair(
                    nb::cast<int>(size_obj[nb::int_(0)]),
                    nb::cast<int>(size_obj[nb::int_(1)])
                );
            }
            if (data.contains("clear_color")) {
                nb::object color_obj = data["clear_color"];
                spec.clear_color = std::array<double, 4>{
                    nb::cast<double>(color_obj[nb::int_(0)]),
                    nb::cast<double>(color_obj[nb::int_(1)]),
                    nb::cast<double>(color_obj[nb::int_(2)]),
                    nb::cast<double>(color_obj[nb::int_(3)])
                };
            }
            if (data.contains("clear_depth")) {
                spec.clear_depth = nb::cast<float>(data["clear_depth"]);
            }
            if (data.contains("format")) {
                spec.format = nb::cast<std::string>(data["format"]);
            }
            return spec;
        }, nb::arg("data"));
}

} // namespace termin
