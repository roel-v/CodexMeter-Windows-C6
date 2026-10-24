#pragma once
#ifdef CODEXMETER_BOARD_C6
#include <lvgl.h>
#include <stddef.h>

// Mapped bytes are immutable, despite legacy themes' non-const pointer fields.
uint8_t* c6_asset_map(const char* path, size_t expected);
void c6_asset_free(void* pointer);
bool c6_asset_image(lv_image_dsc_t* image, uint8_t** pixels,
                    const char* path, int w, int h,
                    lv_color_format_t format = LV_COLOR_FORMAT_RGB565);

struct C6ImagePatch {
  lv_obj_t* image = nullptr;
  lv_image_dsc_t descriptor{};
  uint16_t* pixels = nullptr;
};
bool c6_patch_create(C6ImagePatch* patch, lv_obj_t* parent,
                     const uint8_t* background, int x, int y, int w, int h);
void c6_patch_free(C6ImagePatch* patch);
#endif
