#pragma once

// Battery percentage values: 0..100, unknown (-1), or verified USB-only power.
// Keep USB-only distinct from an attached battery whose gauge is unavailable.
constexpr int BATTERY_USB_POWER = -2;

inline const char* battery_unavailable_text(int percent, bool charging) {
  return percent == BATTERY_USB_POWER ? "USB" : (charging ? "--%+" : "--%");
}
