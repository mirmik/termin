#include "common.hpp"
#include "termin/render/resource_spec.hpp"

namespace termin {

void bind_resource_spec(py::module_& m) {
    py::class_<ResourceSpec>(m, "ResourceSpec")
        .def(py::init<>())
        .def(py::init<std::string, std::string>(),
             py::arg("resource"),
             py::arg("resource_type") = "fbo")
        // Full constructor
        .def(py::init([](
            const std::string& resource,
            const std::string& resource_type,
            py::object size,
            py::object clear_color,
            py::object clear_depth,
            py::object format,
            int samples
        ) {
            ResourceSpec spec;
            spec.resource = resource;
            spec.resource_type = resource_type;
            spec.samples = samples;

            if (!size.is_none()) {
                auto t = size.cast<py::tuple>();
                spec.size = std::make_pair(t[0].cast<int>(), t[1].cast<int>());
            }
            if (!clear_color.is_none()) {
                auto t = clear_color.cast<py::tuple>();
                spec.clear_color = std::array<double, 4>{
                    t[0].cast<double>(), t[1].cast<double>(),
                    t[2].cast<double>(), t[3].cast<double>()
                };
            }
            if (!clear_depth.is_none()) {
                spec.clear_depth = clear_depth.cast<float>();
            }
            if (!format.is_none()) {
                spec.format = format.cast<std::string>();
            }
            return spec;
        }),
            py::arg("resource"),
            py::arg("resource_type") = "fbo",
            py::arg("size") = py::none(),
            py::arg("clear_color") = py::none(),
            py::arg("clear_depth") = py::none(),
            py::arg("format") = py::none(),
            py::arg("samples") = 1
        )
        .def_readwrite("resource", &ResourceSpec::resource)
        .def_readwrite("resource_type", &ResourceSpec::resource_type)
        .def_readwrite("samples", &ResourceSpec::samples)
        // size property: optional<pair<int,int>> <-> tuple or None
        .def_property("size",
            [](const ResourceSpec& self) -> py::object {
                if (self.size) {
                    return py::make_tuple(self.size->first, self.size->second);
                }
                return py::none();
            },
            [](ResourceSpec& self, py::object val) {
                if (val.is_none()) {
                    self.size = std::nullopt;
                } else {
                    auto t = val.cast<py::tuple>();
                    self.size = std::make_pair(t[0].cast<int>(), t[1].cast<int>());
                }
            }
        )
        // clear_color property: optional<array<float,4>> <-> tuple or None
        .def_property("clear_color",
            [](const ResourceSpec& self) -> py::object {
                if (self.clear_color) {
                    auto& c = *self.clear_color;
                    return py::make_tuple(c[0], c[1], c[2], c[3]);
                }
                return py::none();
            },
            [](ResourceSpec& self, py::object val) {
                if (val.is_none()) {
                    self.clear_color = std::nullopt;
                } else {
                    auto t = val.cast<py::tuple>();
                    self.clear_color = std::array<double, 4>{
                        t[0].cast<double>(), t[1].cast<double>(),
                        t[2].cast<double>(), t[3].cast<double>()
                    };
                }
            }
        )
        // clear_depth property: optional<float> <-> float or None
        .def_property("clear_depth",
            [](const ResourceSpec& self) -> py::object {
                if (self.clear_depth) {
                    return py::cast(*self.clear_depth);
                }
                return py::none();
            },
            [](ResourceSpec& self, py::object val) {
                if (val.is_none()) {
                    self.clear_depth = std::nullopt;
                } else {
                    self.clear_depth = val.cast<float>();
                }
            }
        )
        // format property: optional<string> <-> str or None
        .def_property("format",
            [](const ResourceSpec& self) -> py::object {
                if (self.format) {
                    return py::cast(*self.format);
                }
                return py::none();
            },
            [](ResourceSpec& self, py::object val) {
                if (val.is_none()) {
                    self.format = std::nullopt;
                } else {
                    self.format = val.cast<std::string>();
                }
            }
        )
        // serialize() method - returns lists for JSON compatibility
        .def("serialize", [](const ResourceSpec& self) -> py::dict {
            py::dict data;
            data["resource"] = self.resource;
            data["resource_type"] = self.resource_type;
            if (self.size) {
                py::list size_list;
                size_list.append(self.size->first);
                size_list.append(self.size->second);
                data["size"] = size_list;
            }
            if (self.clear_color) {
                auto& c = *self.clear_color;
                py::list color_list;
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
        .def_static("deserialize", [](py::dict data) -> ResourceSpec {
            ResourceSpec spec;
            spec.resource = data.contains("resource") ?
                data["resource"].cast<std::string>() : "";
            spec.resource_type = data.contains("resource_type") ?
                data["resource_type"].cast<std::string>() : "fbo";
            spec.samples = data.contains("samples") ?
                data["samples"].cast<int>() : 1;

            if (data.contains("size")) {
                py::object size_obj = data["size"];
                spec.size = std::make_pair(
                    size_obj[py::int_(0)].cast<int>(),
                    size_obj[py::int_(1)].cast<int>()
                );
            }
            if (data.contains("clear_color")) {
                py::object color_obj = data["clear_color"];
                spec.clear_color = std::array<double, 4>{
                    color_obj[py::int_(0)].cast<double>(),
                    color_obj[py::int_(1)].cast<double>(),
                    color_obj[py::int_(2)].cast<double>(),
                    color_obj[py::int_(3)].cast<double>()
                };
            }
            if (data.contains("clear_depth")) {
                spec.clear_depth = data["clear_depth"].cast<float>();
            }
            if (data.contains("format")) {
                spec.format = data["format"].cast<std::string>();
            }
            return spec;
        }, py::arg("data"));
}

} // namespace termin
