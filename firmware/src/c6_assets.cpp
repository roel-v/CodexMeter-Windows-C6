#include "c6_assets.h"
#ifdef CODEXMETER_BOARD_C6
#include <esp_partition.h>
#include <esp_heap_caps.h>
#include <esp_rom_crc.h>
#include <string.h>
#include "c6_asset_index.h"
#include "config.h"
#include "device_log.h"

namespace {
const uint8_t* mapped = nullptr;
esp_partition_mmap_handle_t mapping;
bool checked[sizeof(C6_ASSETS) / sizeof(C6_ASSETS[0])]{};

bool map_pack() {
  if (mapped) return true;
  const esp_partition_t* part = esp_partition_find_first(
      ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_ANY, "spiffs");
  uint32_t header[5]{};
  if (!part || part->size < C6_ASSET_BYTES ||
      esp_partition_read(part, 0, header, sizeof(header)) != ESP_OK ||
      memcmp(header, "CMASSET1", 8) != 0 ||
      header[2] != C6_ASSET_BYTES || header[3] != C6_ASSET_CRC ||
      header[4] != sizeof(C6_ASSETS) / sizeof(C6_ASSETS[0])) {
    device_logf("ERROR", "C6 artwork missing/mismatched; flash c6_assets.bin");
    return false;
  }
  const void* address = nullptr;
  if (esp_partition_mmap(part, 0, C6_ASSET_BYTES, ESP_PARTITION_MMAP_DATA,
                         &address, &mapping) != ESP_OK) {
    device_logf("ERROR", "C6 artwork map failed");
    return false;
  }
  mapped = static_cast<const uint8_t*>(address);
  device_logf("INFO", "C6 artwork mapped bytes=%u", C6_ASSET_BYTES);
  return true;
}
}

uint8_t* c6_asset_map(const char* path, size_t expected) {
  if (!path || !map_pack()) return nullptr;
  const char* name = strrchr(path, '/');
  name = name ? name + 1 : path;
  for (size_t i = 0; i < sizeof(C6_ASSETS) / sizeof(C6_ASSETS[0]); ++i) {
    const auto& entry = C6_ASSETS[i];
    if (strcmp(name, entry.name) != 0) continue;
    if (entry.size != expected || entry.offset > C6_ASSET_BYTES ||
        entry.size > C6_ASSET_BYTES - entry.offset) return nullptr;
    const uint8_t* data = mapped + entry.offset;
    if (!checked[i]) {
      if (esp_rom_crc32_le(0, data, entry.size) != entry.crc) {
        device_logf("ERROR", "C6 artwork CRC failed %s", name);
        return nullptr;
      }
      checked[i] = true;
    }
    return const_cast<uint8_t*>(data);
  }
  return nullptr;
}

void c6_asset_free(void* pointer) {
  if (!pointer) return;
  const uintptr_t address = reinterpret_cast<uintptr_t>(pointer);
  const uintptr_t start = reinterpret_cast<uintptr_t>(mapped);
  if (mapped && address >= start && address - start < C6_ASSET_BYTES) return;
  heap_caps_free(pointer);
}

bool c6_asset_image(lv_image_dsc_t* image, uint8_t** pixels,
                    const char* path, int w, int h, lv_color_format_t format) {
  const size_t stride = w * (format == LV_COLOR_FORMAT_ARGB8888 ? 4 : 2);
  *pixels = c6_asset_map(path, stride * h);
  if (!*pixels) return false;
  *image = lv_image_dsc_t{};
  image->header.magic = LV_IMAGE_HEADER_MAGIC;
  image->header.cf = format;
  image->header.w = w;
  image->header.h = h;
  image->header.stride = stride;
  image->data_size = stride * h;
  image->data = *pixels;
  return true;
}

bool c6_patch_create(C6ImagePatch* patch, lv_obj_t* parent,
                     const uint8_t* background, int x, int y, int w, int h) {
  patch->pixels = static_cast<uint16_t*>(heap_caps_malloc(w * h * 2, MALLOC_CAP_8BIT));
  if (!patch->pixels) return false;
  for (int row = 0; row < h; ++row) {
    memcpy(patch->pixels + row * w,
           reinterpret_cast<const uint16_t*>(background) + (y + row) * CODEXMETER_SCREEN_W + x,
           w * 2);
  }
  auto& image = patch->descriptor;
  image.header.magic = LV_IMAGE_HEADER_MAGIC;
  image.header.cf = LV_COLOR_FORMAT_RGB565;
  image.header.w = w;
  image.header.h = h;
  image.header.stride = w * 2;
  image.data_size = w * h * 2;
  image.data = reinterpret_cast<const uint8_t*>(patch->pixels);
  patch->image = lv_image_create(parent);
  if (!patch->image) { c6_patch_free(patch); return false; }
  lv_image_set_src(patch->image, &image);
  lv_obj_set_pos(patch->image, x, y);
  return true;
}

void c6_patch_free(C6ImagePatch* patch) {
  // The theme root owns the image object and is deleted before releasing pixels.
  heap_caps_free(patch->pixels);
  *patch = C6ImagePatch{};
}
#endif
