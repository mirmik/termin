#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif

#include <d3d9.h>
#include <wrl/client.h>

#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "tgfx/tgfx2_interop.h"
#include "tgfx2/device_factory.hpp"
#include "tgfx2/i_render_device.hpp"

namespace {
    void require(bool value, const char* message) {
        if (!value)
            throw std::runtime_error(message);
    }

    void require_hr(HRESULT result, const char* operation) {
        if (FAILED(result))
            throw std::runtime_error(std::string(operation) + " failed: HRESULT " +
                                     std::to_string(static_cast<unsigned long>(result)));
    }

    struct InteropClaim {
        tgfx::IRenderDevice& device;
        explicit InteropClaim(tgfx::IRenderDevice& value) : device(value) {
            require(tgfx2_interop_claim_device(&device, this) != 0, "failed to claim test graphics device");
        }
        ~InteropClaim() { tgfx2_interop_release_device(&device, this); }
    };

    struct OwnedTexture {
        tgfx::IRenderDevice& device;
        tgfx::TextureHandle handle;
        ~OwnedTexture() { device.destroy(handle); }
    };

    // Read actual D3D9 shared-surface bytes, without a tgfx sRGB-aware view that
    // could decode them again and accidentally hide missing/double encoding.
    std::vector<uint8_t> read_shared_bgra(void* bridge, uint32_t width, uint32_t height) {
        auto* surface = static_cast<IDirect3DSurface9*>(tgfx2_interop_get_d3d11_d3dimage_surface(bridge));
        require(surface != nullptr, "bridge did not expose a D3D9 surface");
        Microsoft::WRL::ComPtr<IDirect3DDevice9> device;
        require_hr(surface->GetDevice(device.GetAddressOf()), "IDirect3DSurface9::GetDevice");
        Microsoft::WRL::ComPtr<IDirect3DSurface9> staging;
        require_hr(device->CreateOffscreenPlainSurface(width, height, D3DFMT_A8R8G8B8,
                    D3DPOOL_SYSTEMMEM, staging.GetAddressOf(), nullptr), "CreateOffscreenPlainSurface");
        require_hr(device->GetRenderTargetData(surface, staging.Get()), "GetRenderTargetData");
        D3DLOCKED_RECT locked{};
        require_hr(staging->LockRect(&locked, nullptr, D3DLOCK_READONLY), "LockRect");
        std::vector<uint8_t> bytes(static_cast<size_t>(width) * height * 4);
        for (uint32_t row = 0; row < height; ++row)
            std::memcpy(bytes.data() + static_cast<size_t>(row) * width * 4,
                        static_cast<const uint8_t*>(locked.pBits) + static_cast<size_t>(row) * locked.Pitch,
                        static_cast<size_t>(width) * 4);
        require_hr(staging->UnlockRect(), "UnlockRect");
        return bytes;
    }

    int encoded_byte(uint8_t linear_byte) {
        const double linear = linear_byte / 255.0;
        const double srgb = linear <= 0.0031308 ? 12.92 * linear : 1.055 * std::pow(linear, 1.0 / 2.4) - 0.055;
        return static_cast<int>(std::lround(srgb * 255.0));
    }

    void verify_bridge(tgfx::IRenderDevice& device, void* bridge, uint32_t width, uint32_t height,
                       bool encoded_source = false) {
        tgfx::TextureDesc desc;
        desc.width = width;
        desc.height = height;
        desc.format = encoded_source ? tgfx::PixelFormat::RGBA8_sRGB : tgfx::PixelFormat::RGBA8_UNorm;
        desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopySrc | tgfx::TextureUsage::CopyDst;
        OwnedTexture source{device, device.create_texture(desc)};
        require(static_cast<bool>(source.handle), "failed to create linear source texture");
        constexpr std::array<std::array<uint8_t, 4>, 4> colors{{
            {1, 32, 128, 51}, {64, 224, 16, 128}, {128, 64, 192, 204}, {255, 0, 255, 255},
        }};
        std::vector<uint8_t> linear_bytes(static_cast<size_t>(width) * height * 4);
        for (size_t pixel = 0; pixel < linear_bytes.size() / 4; ++pixel)
            std::memcpy(linear_bytes.data() + pixel * 4, colors[pixel % colors.size()].data(), 4);
        device.upload_texture(source.handle, linear_bytes);
        std::vector<float> before(linear_bytes.size()), after(linear_bytes.size());
        require(device.read_texture_rgba_float(source.handle, before.data()), "failed to read linear source");

        // Repeated presentation must not accumulate encoding or mutate the source.
        for (int frame = 0; frame < 2; ++frame) {
            require(tgfx2_interop_present_d3d11_d3dimage_bridge(bridge, source.handle.id) != 0,
                    "D3DImage bridge presentation failed");
            const auto actual = read_shared_bgra(bridge, width, height);
            for (size_t pixel = 0; pixel < actual.size(); pixel += 4) {
                for (size_t channel = 0; channel < 3; ++channel) {
                    const int expected = encoded_source ? linear_bytes[pixel + channel]
                                                        : encoded_byte(linear_bytes[pixel + channel]);
                    const int encoded = actual[pixel + 2 - channel];
                    if (std::abs(encoded - expected) > 1) {
                        std::fprintf(stderr, "D3DImage pixel %zu channel %zu: actual=%d expected=%d linear=%u\n",
                                     pixel / 4, channel, encoded, expected, linear_bytes[pixel + channel]);
                        throw std::runtime_error("bridge must encode linear RGB to sRGB exactly once");
                    }
                }
                require(actual[pixel + 3] == linear_bytes[pixel + 3], "bridge must preserve alpha without encoding");
            }
            require(device.read_texture_rgba_float(source.handle, after.data()) && before == after,
                    "presentation must leave the linear source texture unchanged");
        }
    }
} // namespace

int main() {
    std::unique_ptr<tgfx::IRenderDevice> device;
    try {
        device = tgfx::create_device(tgfx::BackendType::D3D11);
    } catch (const std::exception& error) {
        std::fprintf(stderr, "D3DImage color test unavailable: %s\n", error.what());
        return 77;
    }
    try {
        require(device != nullptr, "D3D11 device is unavailable");
        InteropClaim claim(*device);
        std::unique_ptr<void, decltype(&tgfx2_interop_destroy_d3d11_d3dimage_bridge)> bridge(
            tgfx2_interop_create_d3d11_d3dimage_bridge(4, 3), tgfx2_interop_destroy_d3d11_d3dimage_bridge);
        require(bridge != nullptr, "failed to create D3DImage bridge");
        verify_bridge(*device, bridge.get(), 4, 3);
        verify_bridge(*device, bridge.get(), 4, 3, true);
        require(tgfx2_interop_resize_d3d11_d3dimage_bridge(bridge.get(), 7, 5) != 0, "bridge resize failed");
        verify_bridge(*device, bridge.get(), 7, 5);
        verify_bridge(*device, bridge.get(), 7, 5, true);
        std::printf("D3DImage bridge single sRGB encoding, alpha, source preservation and resize passed\n");
        return 0;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "D3DImage color test failed: %s\n", error.what());
        return 1;
    }
}
