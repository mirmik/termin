#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "texture_data.hpp"
#include "handles.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/material.hpp"

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

            return TextureData(
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

        .def("is_valid", &TextureData::is_valid)

        // Serialization
        .def("direct_serialize", [](const TextureData& self) {
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

                return TextureData(std::move(vec), width, height, channels, false, true, false, path);
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

            return TextureData(std::move(vec), width, height, channels, flip_x, flip_y, transpose);
        }, py::arg("data"));

    // ========== MeshHandle ==========
    py::class_<MeshHandle>(m, "MeshHandle")
        .def(py::init<>())
        .def(py::init<py::object>(), py::arg("asset"))
        .def_static("from_name", &MeshHandle::from_name, py::arg("name"))
        .def_static("from_asset", &MeshHandle::from_asset, py::arg("asset"))
        .def_static("from_mesh3", &MeshHandle::from_mesh3,
            py::arg("mesh"), py::arg("name") = "mesh", py::arg("source_path") = "")
        .def_static("from_mesh", &MeshHandle::from_mesh3,  // alias
            py::arg("mesh"), py::arg("name") = "mesh", py::arg("source_path") = "")
        .def_static("from_vertices_indices", &MeshHandle::from_vertices_indices,
            py::arg("vertices"), py::arg("indices"), py::arg("name") = "mesh")
        .def_static("deserialize", &MeshHandle::deserialize, py::arg("data"))
        .def_readwrite("asset", &MeshHandle::asset)
        .def_property_readonly("is_valid", &MeshHandle::is_valid)
        .def_property_readonly("name", &MeshHandle::name)
        .def_property_readonly("version", &MeshHandle::version)
        .def_property_readonly("mesh", &MeshHandle::mesh)
        .def_property_readonly("gpu", &MeshHandle::gpu, py::return_value_policy::reference)
        .def("get", &MeshHandle::get, py::return_value_policy::reference)
        .def("get_mesh", &MeshHandle::mesh)
        .def("get_mesh_or_none", &MeshHandle::mesh)
        .def("get_asset", [](const MeshHandle& self) { return self.asset; })
        .def("serialize", &MeshHandle::serialize);

    // ========== TextureHandle ==========
    py::class_<TextureHandle>(m, "TextureHandle")
        .def(py::init<>())
        .def(py::init<py::object>(), py::arg("asset"))
        .def_static("from_name", &TextureHandle::from_name, py::arg("name"))
        .def_static("from_asset", &TextureHandle::from_asset, py::arg("asset"))
        .def_static("from_file", &TextureHandle::from_file,
            py::arg("path"), py::arg("name") = "")
        .def_static("from_texture_data", &TextureHandle::from_texture_data,
            py::arg("texture_data"), py::arg("name") = "texture")
        .def_static("deserialize", &TextureHandle::deserialize, py::arg("data"))
        .def_readwrite("asset", &TextureHandle::asset)
        .def_property_readonly("is_valid", &TextureHandle::is_valid)
        .def_property_readonly("name", &TextureHandle::name)
        .def_property_readonly("version", &TextureHandle::version)
        .def_property_readonly("gpu", &TextureHandle::gpu, py::return_value_policy::reference)
        .def_property_readonly("source_path", &TextureHandle::source_path)
        .def("get", &TextureHandle::get, py::return_value_policy::reference)
        .def("get_asset", [](const TextureHandle& self) { return self.asset; })
        .def("bind", &TextureHandle::bind,
            py::arg("graphics"), py::arg("unit") = 0, py::arg("context_key") = 0)
        .def("serialize", &TextureHandle::serialize);

    // ========== MaterialHandle ==========
    py::class_<MaterialHandle>(m, "MaterialHandle")
        .def(py::init<>())
        .def(py::init<py::object>(), py::arg("asset"))
        .def_static("from_direct", &MaterialHandle::from_direct, py::arg("material"),
            py::return_value_policy::reference)
        .def_static("from_asset", &MaterialHandle::from_asset, py::arg("asset"))
        .def_static("from_name", &MaterialHandle::from_name, py::arg("name"))
        .def_static("deserialize", &MaterialHandle::deserialize, py::arg("data"))
        .def_readwrite("_direct", &MaterialHandle::_direct)
        .def_readwrite("asset", &MaterialHandle::asset)
        .def_property_readonly("is_valid", &MaterialHandle::is_valid)
        .def_property_readonly("is_direct", &MaterialHandle::is_direct)
        .def_property_readonly("name", &MaterialHandle::name)
        .def_property_readonly("material", &MaterialHandle::get_material_or_none,
            py::return_value_policy::reference)
        .def("get", &MaterialHandle::get, py::return_value_policy::reference)
        .def("get_asset", [](const MaterialHandle& self) { return self.asset; })
        .def("get_material", &MaterialHandle::get_material, py::return_value_policy::reference)
        .def("get_material_or_none", &MaterialHandle::get_material_or_none,
            py::return_value_policy::reference)
        .def("serialize", &MaterialHandle::serialize);

    // ========== Free functions ==========
    m.def("get_white_texture_handle", &get_white_texture_handle,
        "Get a white 1x1 texture handle (singleton).");
}

} // namespace termin
