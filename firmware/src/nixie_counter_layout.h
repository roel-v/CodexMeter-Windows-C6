#pragma once

#include <stdint.h>
#include <stdio.h>

struct NixieCounterLayout {
  char value[5] = "--";
  char unit[2] = "";
};

// Three digit rollers plus a separate narrow decimal roller and a unit roller.
// Round raw tokens to three significant digits, carrying into the next layout
// or unit when needed. Never truncate high digits or double-round display text.
inline NixieCounterLayout nixie_counter_layout(bool valid, uint64_t tokens) {
  NixieCounterLayout layout;
  if (!valid) return layout;
  const char suffixes[] = {'\0', 'K', 'M', 'B', 'T', 'P', 'E'};
  uint64_t scale = 1;
  int unit = 0;
  while (tokens / scale >= 1000 && unit < 6) {
    scale *= 1000;
    ++unit;
  }
  unsigned precision = unit == 0 ? 1 :
      (tokens / scale < 10 ? 100 : (tokens / scale < 100 ? 10 : 1));
  for (;;) {
    uint64_t step = scale / precision;
    uint64_t rounded = tokens / step;
    if (step > 1 && tokens % step >= step / 2) ++rounded;
    if (rounded >= 1000) {
      if (precision > 1) {
        precision /= 10;
      } else {
        scale *= 1000;
        ++unit;
        precision = 100;
      }
      continue;
    }
    unsigned value = static_cast<unsigned>(rounded);
    if (precision == 100) {
      snprintf(layout.value, sizeof(layout.value), "%u.%02u", value / 100, value % 100);
    } else if (precision == 10) {
      snprintf(layout.value, sizeof(layout.value), "%u.%u", value / 10, value % 10);
    } else {
      snprintf(layout.value, sizeof(layout.value), "%u", value);
    }
    layout.unit[0] = suffixes[unit];
    return layout;
  }
}
