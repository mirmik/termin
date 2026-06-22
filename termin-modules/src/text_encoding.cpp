#include "termin_modules/text_encoding.hpp"

#include <cstdint>

#ifdef _WIN32
    #ifndef NOMINMAX
        #define NOMINMAX
    #endif
    #ifndef WIN32_LEAN_AND_MEAN
        #define WIN32_LEAN_AND_MEAN
    #endif
    #include <windows.h>
#endif

namespace termin_modules {
namespace {

bool is_continuation(unsigned char ch) {
    return (ch & 0xc0) == 0x80;
}

#ifdef _WIN32
std::string wide_to_utf8(const std::wstring& text) {
    if (text.empty()) {
        return {};
    }

    const int size = WideCharToMultiByte(
        CP_UTF8,
        0,
        text.data(),
        static_cast<int>(text.size()),
        nullptr,
        0,
        nullptr,
        nullptr
    );
    if (size <= 0) {
        return {};
    }

    std::string result(static_cast<size_t>(size), '\0');
    WideCharToMultiByte(
        CP_UTF8,
        0,
        text.data(),
        static_cast<int>(text.size()),
        result.data(),
        size,
        nullptr,
        nullptr
    );
    return result;
}

std::string decode_windows_code_page(const std::string& text, UINT code_page) {
    if (text.empty()) {
        return {};
    }

    const int wide_size = MultiByteToWideChar(
        code_page,
        MB_ERR_INVALID_CHARS,
        text.data(),
        static_cast<int>(text.size()),
        nullptr,
        0
    );
    if (wide_size <= 0) {
        return {};
    }

    std::wstring wide(static_cast<size_t>(wide_size), L'\0');
    MultiByteToWideChar(
        code_page,
        MB_ERR_INVALID_CHARS,
        text.data(),
        static_cast<int>(text.size()),
        wide.data(),
        wide_size
    );
    return wide_to_utf8(wide);
}
#endif

std::string replace_invalid_utf8(const std::string& text) {
    std::string result;
    result.reserve(text.size());

    for (size_t i = 0; i < text.size();) {
        const unsigned char ch = static_cast<unsigned char>(text[i]);
        size_t count = 0;
        uint32_t codepoint = 0;

        if (ch < 0x80) {
            result.push_back(text[i++]);
            continue;
        }
        if ((ch & 0xe0) == 0xc0) {
            count = 2;
            codepoint = ch & 0x1f;
        } else if ((ch & 0xf0) == 0xe0) {
            count = 3;
            codepoint = ch & 0x0f;
        } else if ((ch & 0xf8) == 0xf0) {
            count = 4;
            codepoint = ch & 0x07;
        } else {
            result += "\xef\xbf\xbd";
            ++i;
            continue;
        }

        bool valid = i + count <= text.size();
        for (size_t j = 1; valid && j < count; ++j) {
            const unsigned char tail = static_cast<unsigned char>(text[i + j]);
            valid = is_continuation(tail);
            codepoint = (codepoint << 6) | (tail & 0x3f);
        }

        if (valid) {
            valid =
                (count != 2 || codepoint >= 0x80) &&
                (count != 3 || codepoint >= 0x800) &&
                (count != 4 || (codepoint >= 0x10000 && codepoint <= 0x10ffff)) &&
                !(codepoint >= 0xd800 && codepoint <= 0xdfff);
        }

        if (!valid) {
            result += "\xef\xbf\xbd";
            ++i;
            continue;
        }

        result.append(text, i, count);
        i += count;
    }

    return result;
}

} // namespace

bool is_valid_utf8(const std::string& text) {
    for (size_t i = 0; i < text.size();) {
        const unsigned char ch = static_cast<unsigned char>(text[i]);
        size_t count = 0;
        uint32_t codepoint = 0;

        if (ch < 0x80) {
            ++i;
            continue;
        }
        if ((ch & 0xe0) == 0xc0) {
            count = 2;
            codepoint = ch & 0x1f;
        } else if ((ch & 0xf0) == 0xe0) {
            count = 3;
            codepoint = ch & 0x0f;
        } else if ((ch & 0xf8) == 0xf0) {
            count = 4;
            codepoint = ch & 0x07;
        } else {
            return false;
        }

        if (i + count > text.size()) {
            return false;
        }

        for (size_t j = 1; j < count; ++j) {
            const unsigned char tail = static_cast<unsigned char>(text[i + j]);
            if (!is_continuation(tail)) {
                return false;
            }
            codepoint = (codepoint << 6) | (tail & 0x3f);
        }

        if (
            (count == 2 && codepoint < 0x80) ||
            (count == 3 && codepoint < 0x800) ||
            (count == 4 && (codepoint < 0x10000 || codepoint > 0x10ffff)) ||
            (codepoint >= 0xd800 && codepoint <= 0xdfff)
        ) {
            return false;
        }

        i += count;
    }

    return true;
}

std::string sanitize_external_text(const std::string& text) {
    if (text.empty() || is_valid_utf8(text)) {
        return text;
    }

#ifdef _WIN32
    std::string decoded = decode_windows_code_page(text, GetOEMCP());
    if (!decoded.empty() && is_valid_utf8(decoded)) {
        return decoded;
    }

    decoded = decode_windows_code_page(text, GetACP());
    if (!decoded.empty() && is_valid_utf8(decoded)) {
        return decoded;
    }
#endif

    return replace_invalid_utf8(text);
}

} // namespace termin_modules
