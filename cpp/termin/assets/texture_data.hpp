#pragma once

#include <cstdint>
#include <vector>
#include <string>
#include <optional>

namespace termin {

/**
 * Raw image data container.
 *
 * Similar to Mesh3 for meshes - holds CPU data without GPU knowledge.
 */
class TextureData {
public:
    // Image data as contiguous bytes (height * width * channels)
    std::vector<uint8_t> data;
    int width = 0;
    int height = 0;
    int channels = 4;

    // Transform flags for GPU upload
    bool flip_x = false;
    bool flip_y = true;  // OpenGL default
    bool transpose = false;

    // Source path for serialization
    std::string source_path;

    TextureData() = default;

    TextureData(
        std::vector<uint8_t> data_,
        int width_,
        int height_,
        int channels_ = 4,
        bool flip_x_ = false,
        bool flip_y_ = true,
        bool transpose_ = false,
        std::string source_path_ = ""
    ) : data(std::move(data_)),
        width(width_),
        height(height_),
        channels(channels_),
        flip_x(flip_x_),
        flip_y(flip_y_),
        transpose(transpose_),
        source_path(std::move(source_path_)) {}

    /**
     * Create 1x1 white pixel texture.
     */
    static TextureData white_1x1() {
        std::vector<uint8_t> pixel = {255, 255, 255, 255};
        return TextureData(std::move(pixel), 1, 1, 4, false, false, false);
    }

    /**
     * Get transformed data for GPU upload.
     *
     * Returns new data buffer with flip_x/flip_y/transpose applied.
     * Also returns the final width and height after transforms.
     */
    std::tuple<std::vector<uint8_t>, int, int> get_upload_data() const {
        std::vector<uint8_t> result = data;
        int w = width;
        int h = height;

        // Transpose: swap width and height, rearrange pixels
        if (transpose) {
            std::vector<uint8_t> transposed(data.size());
            for (int y = 0; y < height; ++y) {
                for (int x = 0; x < width; ++x) {
                    for (int c = 0; c < channels; ++c) {
                        int src_idx = (y * width + x) * channels + c;
                        int dst_idx = (x * height + y) * channels + c;
                        transposed[dst_idx] = result[src_idx];
                    }
                }
            }
            result = std::move(transposed);
            std::swap(w, h);
        }

        // Flip X: mirror horizontally
        if (flip_x) {
            for (int y = 0; y < h; ++y) {
                for (int x = 0; x < w / 2; ++x) {
                    int x2 = w - 1 - x;
                    for (int c = 0; c < channels; ++c) {
                        int idx1 = (y * w + x) * channels + c;
                        int idx2 = (y * w + x2) * channels + c;
                        std::swap(result[idx1], result[idx2]);
                    }
                }
            }
        }

        // Flip Y: mirror vertically
        if (flip_y) {
            for (int y = 0; y < h / 2; ++y) {
                int y2 = h - 1 - y;
                for (int x = 0; x < w; ++x) {
                    for (int c = 0; c < channels; ++c) {
                        int idx1 = (y * w + x) * channels + c;
                        int idx2 = (y2 * w + x) * channels + c;
                        std::swap(result[idx1], result[idx2]);
                    }
                }
            }
        }

        return {std::move(result), w, h};
    }

    /**
     * Check if data is valid.
     */
    bool is_valid() const {
        return !data.empty() && width > 0 && height > 0 &&
               data.size() == static_cast<size_t>(width * height * channels);
    }
};

} // namespace termin
