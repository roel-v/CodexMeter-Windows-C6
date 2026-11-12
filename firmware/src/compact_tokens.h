#pragma once

#include <stdint.h>
#include <stdio.h>

// Keep Today compact and retain two decimals for 7-day B-and-larger values.
// Round from the original count so a carry can change precision/unit without
// double rounding or overflowing uint64_t by adding a rounding offset.
inline void format_compact_tokens(
    char* output, size_t size, bool valid, uint64_t tokens,
    bool two_decimal_large_units = false) {
  if (!valid) {
    snprintf(output, size, "--");
    return;
  }
  const char* units[] = {"", "K", "M", "B", "T", "P", "E"};
  uint64_t scale = 1;
  unsigned unit = 0;
  while (tokens / scale >= 1000 && unit < 6) {
    scale *= 1000;
    ++unit;
  }
  for (;;) {
    unsigned precision = unit == 0 ? 1 :
        (two_decimal_large_units && unit >= 3 ? 100 :
         (tokens / scale >= 100 ? 1 : 10));
    uint64_t step = scale / precision;
    uint64_t rounded = tokens / step;
    if (step > 1 && tokens % step >= step / 2) ++rounded;
    if (rounded >= 1000 * precision && unit < 6) {
      scale *= 1000;
      ++unit;
      continue;
    }
    // 99.95 rounds to 100, which needs three integer digits, not 100.0.
    if (precision == 10 && rounded >= 1000) {
      precision = 1;
      rounded = tokens / scale + (tokens % scale >= scale / 2);
    }
    if (precision == 100) {
      snprintf(output, size, "%llu.%02llu%s",
          static_cast<unsigned long long>(rounded / 100),
          static_cast<unsigned long long>(rounded % 100), units[unit]);
    } else if (precision == 10 && rounded % 10 != 0) {
      snprintf(output, size, "%llu.%llu%s",
          static_cast<unsigned long long>(rounded / 10),
          static_cast<unsigned long long>(rounded % 10), units[unit]);
    } else {
      snprintf(output, size, "%llu%s",
          static_cast<unsigned long long>(rounded / precision), units[unit]);
    }
    return;
  }
}
