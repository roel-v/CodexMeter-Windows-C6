// Run: c++ -std=c++11 tests/test_nixie_counter.cpp -o /tmp/test_nixie_counter && /tmp/test_nixie_counter
#include "../firmware/src/nixie_counter_layout.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

int main() {
  struct Case {
    bool valid;
    uint64_t tokens;
    const char* value;
    const char* unit;
  };
  const Case cases[] = {
      {false, 1030000000ULL, "--", ""},
      {true, 0, "0", ""},
      {true, 10, "10", ""},
      {true, 999, "999", ""},
      {true, 1000, "1.00", "K"},
      {true, 999499, "999", "K"},
      {true, 999500, "1.00", "M"},
      {true, 12300000, "12.3", "M"},
      {true, 12500000, "12.5", "M"},
      {true, 96200000, "96.2", "M"},
      {true, 99900000, "99.9", "M"},
      {true, 347000000, "347", "M"},
      {true, 999499999, "999", "M"},
      {true, 999500000, "1.00", "B"},
      {true, 1000000000, "1.00", "B"},
      {true, 1029596259, "1.03", "B"},
      {true, 1030000000, "1.03", "B"},
      {true, 1049999999, "1.05", "B"},
      {true, 1050000000, "1.05", "B"},
      {true, 9949999999ULL, "9.95", "B"},
      {true, 9950000000ULL, "9.95", "B"},
      {true, 9990000000ULL, "9.99", "B"},
      {true, 10000000000ULL, "10.0", "B"},
      {true, 12340000000ULL, "12.3", "B"},
      {true, 999499999999ULL, "999", "B"},
      {true, 999500000000ULL, "1.00", "T"},
      {true, 999990000000ULL, "1.00", "T"},
      {true, 1030000000000ULL, "1.03", "T"},
      {true, 1000000000000000ULL, "1.00", "P"},
      {true, 9994999999ULL, "9.99", "B"},
      {true, 9995000000ULL, "10.0", "B"},
      {true, 99949999999ULL, "99.9", "B"},
      {true, 99950000000ULL, "100", "B"},
      {true, UINT64_MAX, "18.4", "E"},
  };
  for (const auto& item : cases) {
    auto layout = nixie_counter_layout(item.valid, item.tokens);
    assert(strcmp(layout.value, item.value) == 0);
    assert(strcmp(layout.unit, item.unit) == 0);
    assert(strlen(layout.value) <= 4);
    const char* decimal = strchr(layout.value, '.');
    if (decimal) {
      assert(decimal - layout.value == 1 || decimal - layout.value == 2);
      assert(strlen(layout.value) == 4);
    } else {
      assert(strlen(layout.value) <= 3);
    }
    assert(layout.value[0] != '.');
  }
  printf("%zu nixie counter cases passed\n", sizeof(cases) / sizeof(cases[0]));
}
