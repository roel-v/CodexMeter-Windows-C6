// Share internal RAM with transient LVGL layers instead of reserving a fixed pool.
#include <lvgl.h>
#if defined(CODEXMETER_BOARD_C6) && LV_USE_STDLIB_MALLOC == LV_STDLIB_CUSTOM
#include <esp_heap_caps.h>
#include <string.h>

extern "C" {
void lv_mem_init(void) {}
void lv_mem_deinit(void) {}
lv_mem_pool_t lv_mem_add_pool(void*, size_t) { return nullptr; }
void lv_mem_remove_pool(lv_mem_pool_t) {}
void* lv_malloc_core(size_t size) {
  return heap_caps_malloc(size, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
}
void* lv_realloc_core(void* pointer, size_t size) {
  return heap_caps_realloc(pointer, size, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
}
void lv_free_core(void* pointer) { heap_caps_free(pointer); }
void lv_mem_monitor_core(lv_mem_monitor_t* monitor) {
  multi_heap_info_t info{};
  heap_caps_get_info(&info, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
  memset(monitor, 0, sizeof(*monitor));
  monitor->total_size = info.total_free_bytes + info.total_allocated_bytes;
  monitor->free_cnt = info.free_blocks;
  monitor->free_size = info.total_free_bytes;
  monitor->free_biggest_size = info.largest_free_block;
  monitor->used_cnt = info.allocated_blocks;
  monitor->max_used = monitor->total_size - info.minimum_free_bytes;
  monitor->used_pct = monitor->total_size ? 100 - info.total_free_bytes * 100 / monitor->total_size : 0;
  monitor->frag_pct = info.total_free_bytes ? 100 - info.largest_free_block * 100 / info.total_free_bytes : 0;
}
lv_result_t lv_mem_test_core(void) {
  return heap_caps_check_integrity(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT, false)
      ? LV_RESULT_OK : LV_RESULT_INVALID;
}
}
#endif
