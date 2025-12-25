#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "termin/assets/texture_data.hpp"

namespace py = pybind11;

namespace {

void bind_texture_data(py::module_& m) {
    py::class_<termin::TextureData>(m, "TextureData")
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

            return termin::TextureData(
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
        .def_readwrite("width", &termin::TextureData::width)
        .def_readwrite("height", &termin::TextureData::height)
        .def_readwrite("channels", &termin::TextureData::channels)
        .def_readwrite("flip_x", &termin::TextureData::flip_x)
        .def_readwrite("flip_y", &termin::TextureData::flip_y)
        .def_readwrite("transpose", &termin::TextureData::transpose)
        .def_readwrite("source_path", &termin::TextureData::source_path)

        // Data as numpy array property
        .def_property("data",
            [](const termin::TextureData& self) {
                // Return as numpy array with shape (height, width, channels)
                return py::array_t<uint8_t>(
                    {self.height, self.width, self.channels},
                    {self.width * self.channels * sizeof(uint8_t),
                     self.channels * sizeof(uint8_t),
                     sizeof(uint8_t)},
                    self.data.data()
                );
            },
            [](termin::TextureData& self, py::array_t<uint8_t> arr) {
                py::buffer_info info = arr.request();
                uint8_t* ptr = static_cast<uint8_t*>(info.ptr);
                size_t size = info.size;
                self.data.assign(ptr, ptr + size);
            }
        )

        // Static factory methods
        .def_static("white_1x1", &termin::TextureData::white_1x1)

        .def_static("from_file", [](const std::string& path) {
            // Load image via PIL
            py::object PIL = py::module_::import("PIL.Image");
            py::object image = PIL.attr("open")(path).attr("convert")("RGBA");
            py::object np = py::module_::import("numpy");
            py::array_t<uint8_t> data = np.attr("array")(image, py::arg("dtype") = np.attr("uint8"));

            py::buffer_info info = data.request();
            int height = static_cast<int>(info.shape[0]);
            int width = static_cast<int>(info.shape[1]);
            int channels = static_cast<int>(info.shape[2]);

            uint8_t* ptr = static_cast<uint8_t*>(info.ptr);
            std::vector<uint8_t> vec(ptr, ptr + info.size);

            // Load spec for flip settings
            py::object spec_module = py::module_::import("termin.loaders.texture_spec");
            py::object spec = spec_module.attr("TextureSpec").attr("for_texture_file")(path);
            bool flip_x = spec.attr("flip_x").cast<bool>();
            bool flip_y = spec.attr("flip_y").cast<bool>();
            bool transpose = spec.attr("transpose").cast<bool>();

            return termin::TextureData(
                std::move(vec),
                width, height, channels,
                flip_x, flip_y, transpose,
                path
            );
        }, py::arg("path"))

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

            return termin::TextureData(
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
        .def("get_upload_data", [](const termin::TextureData& self) {
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

        .def("is_valid", &termin::TextureData::is_valid)

        // Serialization
        .def("direct_serialize", [](const termin::TextureData& self) {
            py::dict result;
            if (!self.source_path.empty()) {
                result["type"] = "path";
                result["path"] = self.source_path;
            } else {
                // Inline serialization via base64
                py::object base64 = py::module_::import("base64");
                py::bytes data_bytes(reinterpret_cast<const char*>(self.data.data()), self.data.size());
                py::object data_b64 = base64.attr("b64encode")(data_bytes).attr("decode")("ascii");

                result["type"] = "inline";
                result["width"] = self.width;
                result["height"] = self.height;
                result["channels"] = self.channels;
                result["flip_x"] = self.flip_x;
                result["flip_y"] = self.flip_y;
                result["transpose"] = self.transpose;
                result["data_b64"] = data_b64;
            }
            return result;
        })

        .def_static("direct_deserialize", [](const py::dict& data) {
            std::string type = data.contains("type") ? data["type"].cast<std::string>() : "inline";

            if (type == "path") {
                std::string path = data["path"].cast<std::string>();
                // Load via from_file
                py::object PIL = py::module_::import("PIL.Image");
                py::object image = PIL.attr("open")(path).attr("convert")("RGBA");
                py::object np = py::module_::import("numpy");
                py::array_t<uint8_t> arr = np.attr("array")(image, py::arg("dtype") = np.attr("uint8"));

                py::buffer_info info = arr.request();
                int height = static_cast<int>(info.shape[0]);
                int width = static_cast<int>(info.shape[1]);
                int channels = static_cast<int>(info.shape[2]);

                uint8_t* ptr = static_cast<uint8_t*>(info.ptr);
                std::vector<uint8_t> vec(ptr, ptr + info.size);

                return termin::TextureData(std::move(vec), width, height, channels, false, true, false, path);
            }

            // Inline deserialization
            int width = data["width"].cast<int>();
            int height = data["height"].cast<int>();
            int channels = data.contains("channels") ? data["channels"].cast<int>() : 4;

            py::object base64 = py::module_::import("base64");
            py::bytes data_bytes = base64.attr("b64decode")(data["data_b64"]);
            std::string bytes_str = data_bytes.cast<std::string>();
            std::vector<uint8_t> vec(bytes_str.begin(), bytes_str.end());

            bool flip_x = data.contains("flip_x") ? data["flip_x"].cast<bool>() : false;
            bool flip_y = data.contains("flip_y") ? data["flip_y"].cast<bool>() : true;
            bool transpose = data.contains("transpose") ? data["transpose"].cast<bool>() : false;

            return termin::TextureData(std::move(vec), width, height, channels, flip_x, flip_y, transpose);
        }, py::arg("data"));
}

} // anonymous namespace

PYBIND11_MODULE(_texture_native, m) {
    m.doc() = "Native C++ texture module (TextureData)";

    // Bind TextureData
    bind_texture_data(m);
}
