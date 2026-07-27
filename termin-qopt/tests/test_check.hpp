#pragma once

#include <cstdio>
#include <cstdlib>

[[noreturn]] inline void termin_qopt_test_failure(const char *expression,
                                                  const char *file, int line) {
  std::fprintf(stderr, "%s:%d: termin-qopt test check failed: %s\n", file, line,
               expression);
  std::abort();
}

#define TERMIN_QOPT_CHECK(expression)                                          \
  do {                                                                         \
    if (!(expression)) {                                                       \
      termin_qopt_test_failure(#expression, __FILE__, __LINE__);               \
    }                                                                          \
  } while (false)
