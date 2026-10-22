#pragma once

#include <lvgl.h>

// Preserve the theme's font, height and preferred proportions unless the full
// value would overflow. The caller reserves space for any separate unit/gap.
inline int fit_label_scale_x(lv_obj_t* label, int preferred, int available) {
  lv_obj_update_layout(label);
  int width = lv_obj_get_width(label);
  if (width <= 0) return preferred;
  int fitted = available * 256 / width;
  if (fitted < 1) fitted = 1;
  return fitted < preferred ? fitted : preferred;
}
