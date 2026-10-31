#include "touch_input.h"
#include "touch_geometry.h"
#include "config.h"
#include "device_log.h"
#include "imu.h"
#include "ui.h"
#include <Wire.h>

namespace {
bool ready = false, down = false, cancelled = false;
uint32_t last_poll = 0, last_point = 0, started = 0;
int start_x = 0, start_y = 0, end_x = 0, end_y = 0, max_move = 0;
uint8_t start_rotation = 0;
uint32_t frames = 0, points_seen = 0;
}

void touch_input_init() {
#ifdef CODEXMETER_BOARD_C6
  // Waveshare Arduino-v3.3.3/09_LVGL_V9_Test: CST9220, reset GPIO11, IRQ5.
  pinMode(11, OUTPUT);
  digitalWrite(11, HIGH); delay(200);
  digitalWrite(11, LOW); delay(200);
  digitalWrite(11, HIGH); delay(200);
  pinMode(5, INPUT_PULLUP);
  Wire.beginTransmission(0x5A);
  ready = Wire.endTransmission() == 0;
  device_logf(ready ? "INFO" : "WARN", "CST9220 touch ready=%d", ready);
#endif
}

void touch_input_tick(bool display_active) {
  if (!ready) return;
  uint32_t now = millis();
  if (!display_active) { down = false; cancelled = true; return; }
  if (now - last_poll < 20) return;
  last_poll = now;
  bool pressed = false;
  bool frame = false;
  uint8_t data[10]{};
  Wire.beginTransmission(0x5A);
  Wire.write(0xD0); Wire.write(0x00);
  if (Wire.endTransmission(false) == 0 && Wire.requestFrom((uint8_t)0x5A, (uint8_t)10) == 10) {
    for (auto& value : data) value = Wire.read();
    Wire.beginTransmission(0x5A);
    Wire.write(0xD0); Wire.write(0x00); Wire.write(0xAB);
    Wire.endTransmission();
    frame = data[6] == 0xAB;
    if (frame) ++frames;
    int points = data[5] & 0x7F;
    if (frame && points > 1) cancelled = true;
    pressed = frame && points == 1 && (data[0] & 0x0F) == 0x06;
  }
  if (pressed) {
    ++points_seen;
    int raw_x = ((int)data[1] << 4) | (data[3] >> 4);
    int raw_y = ((int)data[2] << 4) | (data[3] & 0x0F);
    if (raw_x >= 480 || raw_y >= 480) { cancelled = true; return; }
    // Vendor axes: swap XY and invert physical X (with zero-based bounds).
    int x = 479 - raw_y, y = raw_x;
    uint8_t rotation = imu_rotation_quadrant();
    touch_to_logical(x, y, rotation);
    if (!down) {
      down = true; cancelled = false; max_move = 0;
      start_x = x; start_y = y; start_rotation = rotation; started = now;
    }
    if (start_rotation != rotation) cancelled = true;
    end_x = x; end_y = y; last_point = now;
    max_move = max(max_move, max(abs(x - start_x), abs(y - start_y)));
  } else if (down && ((frame && (data[5] & 0x7F) == 0) || now - last_point > 120)) {
    down = false;
    if (!cancelled && start_rotation == imu_rotation_quadrant() && now - started < 2000) {
      bool tap = max_move < 18 && now - started < 700;
      ui_touch_gesture(end_x - start_x, end_y - start_y, end_x, end_y, tap);
    }
  }
}

void touch_input_diagnostics() {
  const int expected[4][2] = {{10,20}, {20,469}, {469,459}, {459,10}};
  bool geometry_ok = true;
  for (int r = 0; r < 4; ++r) {
    int x = 10, y = 20;
    touch_to_logical(x, y, r);
    geometry_ok = geometry_ok && x == expected[r][0] && y == expected[r][1];
  }
  Serial.printf("TOUCH ready=%d frames=%lu points=%lu geometry=%d x=%d y=%d\n",
      ready, (unsigned long)frames, (unsigned long)points_seen, geometry_ok, end_x, end_y);
}
