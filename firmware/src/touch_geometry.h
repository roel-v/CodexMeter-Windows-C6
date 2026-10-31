#pragma once
#include <stdint.h>

// Inverse of display_rotation_draw after the C6 vendor's panel-axis transform.
inline void touch_to_logical(int& x, int& y, uint8_t rotation) {
  int px = x, py = y;
  switch (rotation & 3) {
    case 1: x = py; y = 479 - px; break;
    case 2: x = 479 - px; y = 479 - py; break;
    case 3: x = 479 - py; y = px; break;
  }
}
