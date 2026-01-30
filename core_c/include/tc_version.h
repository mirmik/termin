// tc_version.h - Termin version info
//
// Increment TC_VERSION when any ABI-breaking change is made!
// This triggers recompilation of external modules.

#ifndef TC_VERSION_H
#define TC_VERSION_H

#define TC_VERSION_MAJOR 0
#define TC_VERSION_MINOR 1
#define TC_VERSION_PATCH 8

// stringifyd version
#define TC_VERSION_XSTRING(s) TC_VERSION_STRINGIFY(s)
#define TC_VERSION_STRINGIFY(s) #s

#define TC_VERSION_STRING TC_VERSION_XSTRING(TC_VERSION_MAJOR) "." TC_VERSION_XSTRING(TC_VERSION_MINOR) "." TC_VERSION_XSTRING(TC_VERSION_PATCH)

// Single integer version for compatibility checks
#define TC_VERSION ((int)((TC_VERSION_MAJOR << 16) | (TC_VERSION_MINOR << 8) | (TC_VERSION_PATCH)))

#endif // TC_VERSION_H
