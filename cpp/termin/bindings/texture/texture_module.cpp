#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/ndarray.h>
#include <cstring>

#include "termin/assets/texture_data.hpp"

namespace nb = nanobind;

namespace {

void bind_texture_data(nb::module_& m) {
    nb::class_<termin::TextureData>(m, "TextureData")
        .def(nb::init<>())
        .def("__init__", [](
            termin::TextureData* self,
            nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> data,
            int width,
            int height,
            int channels,
            bool flip_x,
            bool flip_y,
            bool transpose,
            const std::string& source_path
        ) {
            // Convert ndarray to vector
            uint8_t* ptr = data.data();
            size_t size = data.size();
            std::vector<uint8_t> vec(ptr, ptr + size);

            new (self) termin::TextureData(
                std::move(vec),
                width, height, channels,
                flip_x, flip_y, transpose,
                source_path
            );
        },
            nb::arg("data"),
            nb::arg("width"),
            nb::arg("height"),
            nb::arg("channels") = 4,
            nb::arg("flip_x") = false,
            nb::arg("flip_y") = true,
            nb::arg("transpose") = false,
            nb::arg("source_path") = ""
        )

        // Properties
        .def_rw("width", &termin::TextureData::width)
        .def_rw("height", &termin::TextureData::height)
        .def_rw("channels", &termin::TextureData::channels)
        .def_rw("flip_x", &termin::TextureData::flip_x)
        .def_rw("flip_y", &termin::TextureData::flip_y)
        .def_rw("transpose", &termin::TextureData::transpose)
        .def_rw("source_path", &termin::TextureData::source_path)

        // Data as numpy array property
        .def_prop_rw("data",
            [](const termin::TextureData& self) {
                // Return as numpy array with shape (height, width, channels)
                size_t shape[3] = {
                    static_cast<size_t>(self.height),
                    static_cast<size_t>(self.width),
                    static_cast<size_t>(self.channels)
                };
                return nb::ndarray<nb::numpy, const uint8_t, nb::shape<-1, -1, -1>>(
                    self.data.data(),
                    3,
                    shape
                );
            },
            [](termin::TextureData& self, nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> arr) {
                uint8_t* ptr = arr.data();
                size_t size = arr.size();
                self.data.assign(ptr, ptr + size);
            }
        )

        // Static factory methods
        .def_static("white_1x1", &termin::TextureData::white_1x1)

        .def_static("from_file", [](const std::string& path) {
            // Load image via PIL
            nb::object PIL = nb::module_::import_("PIL.Image");
            nb::object image = PIL.attr("open")(path).attr("convert")("RGBA");
            nb::object np = nb::module_::import_("numpy");
            nb::object data_obj = np.attr("array")(image, nb::arg("dtype") = np.attr("uint8"));

            // Cast to ndarray
            auto data = nb::cast<nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu>>(data_obj);

            int height = static_cast<int>(data.shape(0));
            int width = static_cast<int>(data.shape(1));
            int channels = static_cast<int>(data.shape(2));

            uint8_t* ptr = data.data();
            std::vector<uint8_t> vec(ptr, ptr + data.size());

            // Load spec for flip settings
            nb::object spec_module = nb::module_::import_("termin.loaders.texture_spec");
            nb::object spec = spec_module.attr("TextureSpec").attr("for_texture_file")(path);
            bool flip_x = nb::cast<bool>(spec.attr("flip_x"));
            bool flip_y = nb::cast<bool>(spec.attr("flip_y"));
            bool transpose = nb::cast<bool>(spec.attr("transpose"));

            return termin::TextureData(
                std::move(vec),
                width, height, channels,
                flip_x, flip_y, transpose,
                path
            );
        }, nb::arg("path"))

        .def_static("from_array", [](
            nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> data,
            bool flip_x,
            bool flip_y,
            bool transpose
        ) {
            if (data.ndim() != 3) {
                throw std::runtime_error("Expected 3D array (height, width, channels)");
            }

            int height = static_cast<int>(data.shape(0));
            int width = static_cast<int>(data.shape(1));
            int channels = static_cast<int>(data.shape(2));

            uint8_t* ptr = data.data();
            size_t size = data.size();
            std::vector<uint8_t> vec(ptr, ptr + size);

            return termin::TextureData(
                std::move(vec),
                width, height, channels,
                flip_x, flip_y, transpose
            );
        },
            nb::arg("data"),
            nb::arg("flip_x") = false,
            nb::arg("flip_y") = true,
            nb::arg("transpose") = false
        )

        // Methods
        .def("get_upload_data", [](const termin::TextureData& self) {
            auto [data, w, h] = self.get_upload_data();

            // Copy data and return as numpy array
            size_t size = data.size();
            uint8_t* buf = new uint8_t[size];
            std::memcpy(buf, data.data(), size);

            size_t shape[3] = {
                static_cast<size_t>(h),
                static_cast<size_t>(w),
                static_cast<size_t>(self.channels)
            };

            nb::capsule owner(buf, [](void* p) noexcept {
                delete[] static_cast<uint8_t*>(p);
            });

            auto arr = nb::ndarray<nb::numpy, uint8_t, nb::shape<-1, -1, -1>>(
                buf, 3, shape, owner
            );

            return nb::make_tuple(arr, nb::make_tuple(w, h));
        })

        .def("is_valid", &termin::TextureData::is_valid)

        // Serialization
        .def("direct_serialize", [](const termin::TextureData& self) {
            nb::dict result;
            if (!self.source_path.empty()) {
                result["type"] = "path";
                result["path"] = self.source_path;
            } else {
                // Inline serialization via base64
                nb::object base64 = nb::module_::import_("base64");
                nb::bytes data_bytes(reinterpret_cast<const char*>(self.data.data()), self.data.size());
                nb::object data_b64 = base64.attr("b64encode")(data_bytes).attr("decode")("ascii");

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

        .def_static("direct_deserialize", [](const nb::dict& data) {
            std::string type = data.contains("type") ? nb::cast<std::string>(data["type"]) : "inline";

            if (type == "path") {
                std::string path = nb::cast<std::string>(data["path"]);
                // Load via from_file
                nb::object PIL = nb::module_::import_("PIL.Image");
                nb::object image = PIL.attr("open")(path).attr("convert")("RGBA");
                nb::object np = nb::module_::import_("numpy");
                nb::object arr_obj = np.attr("array")(image, nb::arg("dtype") = np.attr("uint8"));

                auto arr = nb::cast<nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu>>(arr_obj);

                int height = static_cast<int>(arr.shape(0));
                int width = static_cast<int>(arr.shape(1));
                int channels = static_cast<int>(arr.shape(2));

                uint8_t* ptr = arr.data();
                std::vector<uint8_t> vec(ptr, ptr + arr.size());

                return termin::TextureData(std::move(vec), width, height, channels, false, true, false, path);
            }

            // Inline deserialization
            int width = nb::cast<int>(data["width"]);
            int height = nb::cast<int>(data["height"]);
            int channels = data.contains("channels") ? nb::cast<int>(data["channels"]) : 4;

            nb::object base64 = nb::module_::import_("base64");
            nb::bytes data_bytes = nb::cast<nb::bytes>(base64.attr("b64decode")(data["data_b64"]));
            const char* bytes_ptr = data_bytes.c_str();
            size_t bytes_len = data_bytes.size();
            std::vector<uint8_t> vec(bytes_ptr, bytes_ptr + bytes_len);

            bool flip_x = data.contains("flip_x") ? nb::cast<bool>(data["flip_x"]) : false;
            bool flip_y = data.contains("flip_y") ? nb::cast<bool>(data["flip_y"]) : true;
            bool transpose = data.contains("transpose") ? nb::cast<bool>(data["transpose"]) : false;

            return termin::TextureData(std::move(vec), width, height, channels, flip_x, flip_y, transpose);
        }, nb::arg("data"));
}

} // anonymous namespace

NB_MODULE(_texture_native, m) {
    m.doc() = "Native C++ texture module (TextureData)";

    // Bind TextureData
    bind_texture_data(m);
}
