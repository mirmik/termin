// tc_version.h - Termin version info
//
// Increment TC_VERSION when any ABI-breaking change is made!
// This triggers recompilation of external modules.

#ifndef TC_VERSION_H
#define TC_VERSION_H

#define TC_VERSION_MAJOR 0
#define TC_VERSION_MINOR 1
#define TC_VERSION_PATCH 1
#define TC_VERSION_STRING "0.1.1"

// Single integer version for compatibility checks
// INCREMENT THIS when any ABI-breaking change is made!
#define TC_VERSION 1

#endif // TC_VERSION_H
