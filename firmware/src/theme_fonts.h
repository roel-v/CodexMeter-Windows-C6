#pragma once
#include <lvgl.h>
#include <esp_heap_caps.h>
#include "c6_assets.h"

#ifdef CODEXMETER_BOARD_C6
lv_font_t* c6_font_get(const char* path, int size);
// Keep each theme's font selection and metrics, with flash-resident bitmaps.
#define lv_tiny_ttf_create_file_ex(path, size, kerning, cache) c6_font_get(path, size)
inline void theme_asset_free(void* data) { c6_asset_free(data); }
#else
inline void theme_asset_free(void* data) { heap_caps_free(data); }
#endif
