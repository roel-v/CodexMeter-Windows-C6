#pragma once
#include <Arduino_GFX_Library.h>
#include "config.h"

#if defined(CODEXMETER_BOARD_BALL)
class CodexMeterPanel : public Arduino_GC9A01 {
 public:
  explicit CodexMeterPanel(Arduino_DataBus* bus) : Arduino_GC9A01(bus, 38, 0, true) {}
  bool begin(int32_t speed = 40000000) override {
    pinMode(42, OUTPUT); digitalWrite(42, HIGH);
    bool ok = Arduino_GC9A01::begin(speed); invertDisplay(false); return ok;
  }
  void setBrightness(uint8_t value) { analogWrite(42, 255-value); }
  void displayOff() override { setBrightness(0); Arduino_GC9A01::displayOff(); }
};
#elif defined(CODEXMETER_BOARD_C6)
using CodexMeterPanel = Arduino_SH8601;
#else
using CodexMeterPanel = Arduino_CO5300;
#endif
