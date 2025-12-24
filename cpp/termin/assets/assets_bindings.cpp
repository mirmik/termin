#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "texture_data.hpp"

namespace py = pybind11;

namespace termin {

void bind_assets(py::module_& m) {
    py::class_<TextureData>(m, "TextureData")
        .def(py::init<>())
        .def(py::init([](
            py::array_t<uint8_t> data,
            int width,
            int height,
            int channels,
            bool flip_x,
            bool flip_y,
            bool transpose,
            const std::string& source_path
        ) {
            // Convert numpy array to vector
            py::buffer_info info = data.request();
            uint8_t* ptr = static_cast<uint8_t*>(info.ptr);
            size_t size = info.size;
            std::vector<uint8_t> vec(ptr, ptr + size);

            return TextureData(
                std::move(vec),
                width, height, channels,
                flip_x, flip_y, transpose,
                source_path
            );
        }),
            py::arg("data"),
            py::arg("width"),
            py::arg("height"),
            py::arg("channels") = 4,
            py::arg("flip_x") = false,
            py::arg("flip_y") = true,
            py::arg("transpose") = false,
            py::arg("source_path") = ""
        )

        // Properties
        .def_readwrite("width", &TextureData::width)
        .def_readwrite("height", &TextureData::height)
        .def_readwrite("channels", &TextureData::channels)
        .def_readwrite("flip_x", &TextureData::flip_x)
        .def_readwrite("flip_y", &TextureData::flip_y)
        .def_readwrite("transpose", &TextureData::transpose)
        .def_readwrite("source_path", &TextureData::source_path)

        // Data as numpy array property
        .def_property("data",
            [](const TextureData& self) {
                // Return as numpy array with shape (height, width, channels)
                return py::array_t<uint8_t>(
                    {self.height, self.width, self.channels},
                    {self.width * self.channels * sizeof(uint8_t),
                     self.channels * sizeof(uint8_t),
                     sizeof(uint8_t)},
                    self.data.data()
                );
            },
            [](TextureData& self, py::array_t<uint8_t> arr) {
                py::buffer_info info = arr.request();
                uint8_t* ptr = static_cast<uint8_t*>(info.ptr);
                size_t size = info.size;
                self.data.assign(ptr, ptr + size);
            }
        )

        // Static factory methods
        .def_static("white_1x1", &TextureData::white_1x1)

        .def_static("from_array", [](
            py::array_t<uint8_t> data,
            bool flip_x,
            bool flip_y,
            bool transpose
        ) {
            py::buffer_info info = data.request();
            if (info.ndim != 3) {
                throw std::runtime_error("Expected 3D array (height, width, channels)");
            }

            int height = static_cast<int>(info.shape[0]);
            int width = static_cast<int>(info.shape[1]);
            int channels = static_cast<int>(info.shape[2]);

            uint8_t* ptr = static_cast<uint8_t*>(info.ptr);
            size_t size = info.size;
            std::vector<uint8_t> vec(ptr, ptr + size);

            return TextureData(
                std::move(vec),
                width, height, channels,
                flip_x, flip_y, transpose
            );
        },
            py::arg("data"),
            py::arg("flip_x") = false,
            py::arg("flip_y") = true,
            py::arg("transpose") = false
        )

        // Methods
        .def("get_upload_data", [](const TextureData& self) {
            auto [data, w, h] = self.get_upload_data();

            // Return as (numpy array, (width, height))
            py::array_t<uint8_t> arr(
                {h, w, self.channels},
                {w * self.channels * sizeof(uint8_t),
                 self.channels * sizeof(uint8_t),
                 sizeof(uint8_t)},
                data.data()
            );
            // Copy data since 'data' will be destroyed
            py::array_t<uint8_t> result({h, w, self.channels});
            std::memcpy(result.mutable_data(), data.data(), data.size());

            return py::make_tuple(result, py::make_tuple(w, h));
        })

        .def("is_valid", &TextureData::is_valid);
}

} // namespace termin
