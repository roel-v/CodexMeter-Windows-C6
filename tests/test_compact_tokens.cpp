// Run: c++ -std=c++11 tests/test_compact_tokens.cpp -o /tmp/test_compact_tokens && /tmp/test_compact_tokens
#include "../firmware/src/compact_tokens.h"

#include <assert.h>
#include <initializer_list>
#include <string.h>

int main() {
  struct Case { uint64_t tokens; const char* today; const char* week; };
  const Case cases[] = {
      {0, "0", "0"}, {999, "999", "999"}, {1000, "1K", "1K"},
      {1030, "1K", "1K"}, {1234, "1.2K", "1.2K"},
      {99949, "99.9K", "99.9K"}, {99950, "100K", "100K"},
      {999499, "999K", "999K"}, {999500, "1M", "1M"},
      {96200000, "96.2M", "96.2M"},
      {999499999, "999M", "999M"},
      {999500000, "1B", "1.00B"}, {999999999, "1B", "1.00B"},
      {1000000000, "1B", "1.00B"}, {1030000000, "1B", "1.03B"},
      {12340000000, "12.3B", "12.34B"},
      {99950000000, "100B", "99.95B"},
      {123450000000, "123B", "123.45B"},
      {999500000000, "1T", "999.50B"},
      {999990000000, "1T", "999.99B"},
      {999994999999, "1T", "999.99B"},
      {999995000000, "1T", "1.00T"},
      {999500000000000, "1P", "999.50T"},
      {999995000000000, "1P", "1.00P"},
      {999995000000000000, "1E", "1.00E"},
      {UINT64_MAX, "18.4E", "18.45E"},
  };
  char text[24];
  format_compact_tokens(text, sizeof(text), false, 123);
  assert(strcmp(text, "--") == 0);
  for (const auto& c : cases) {
    format_compact_tokens(text, sizeof(text), true, c.tokens);
    assert(strcmp(text, c.today) == 0);
    format_compact_tokens(text, sizeof(text), true, c.tokens, true);
    assert(strcmp(text, c.week) == 0);
  }
  // Today's mechanical display has three digit rollers and a narrow decimal
  // roller before the final digit. Exercise boundaries and the full uint64 range.
  auto check = [&](uint64_t tokens) {
    format_compact_tokens(text, sizeof(text), true, tokens);
    unsigned digits = 0;
    for (const char* p = text; *p; ++p) {
      if (*p >= '0' && *p <= '9') ++digits;
      if (*p == '.') assert(strlen(p) == 3);
    }
    assert(digits <= 3);
    assert(strstr(text, "1000") == nullptr);
  };
  for (uint64_t scale = 1; scale <= 1000000000000000000ULL; scale *= 1000) {
    if (scale > 1) {
      uint64_t step = scale / 1000;
      for (uint64_t n : {99949ULL, 99950ULL, 999499ULL, 999500ULL}) {
        if (step <= UINT64_MAX / n) {
          uint64_t boundary = step * n;
          check(boundary - 1); check(boundary); check(boundary + 1);
        }
      }
    }
    if (scale == 1000000000000000000ULL) break;
  }
  uint64_t sample = 123456789;
  for (unsigned i = 0; i < 100000; ++i) {
    sample = sample * 6364136223846793005ULL + 1;
    check(sample);
  }
  printf("Compact token formatting: %zu cases and 100000 samples passed\n",
      sizeof(cases) / sizeof(cases[0]));
}
