#include "identity.h"

#include <Arduino.h>
#include <esp_mac.h>

#include "config.h"

static bool initialized = false;
static char device_id[32];
static char short_id[8];
static char ble_name[32];
static char json[513];

void identity_init() {
  if (initialized) return;

  // C6 eFuse MAC is EUI-64; the protocol requires the six-byte Wi-Fi MAC.
  // Pack in the original ESP.getEfuseMac() byte order to preserve S3 IDs.
  uint8_t mac[6] = {};
  ESP_ERROR_CHECK(esp_read_mac(mac, ESP_MAC_WIFI_STA));
  uint64_t chip = 0;
  for (size_t i = 0; i < sizeof(mac); ++i) {
    chip |= (uint64_t)mac[i] << (8 * i);
  }
  uint32_t short_value = (uint32_t)((chip >> 24) & 0xFFFFFFULL);
  snprintf(device_id, sizeof(device_id), "codexmeter-%012llx",
           (unsigned long long)chip);
  snprintf(short_id, sizeof(short_id), "%06lX", (unsigned long)short_value);
  snprintf(ble_name, sizeof(ble_name), "%s-%s", CODEXMETER_DEVICE_NAME, short_id);
#ifdef CODEXMETER_BOARD_BALL
  int length = snprintf(json,sizeof(json),
      "{\"device_id\":\"%s\",\"short_id\":\"%s\",\"name\":\"%s\","
      "\"model\":\"spotpear_ball_v2\",\"firmware\":\"3.12.3.0\",\"protocol\":1,"
      "\"width\":240,\"height\":240,\"capabilities\":[\"brightness\",\"rotation\",\"touch\",\"screen\"]}",
      device_id,short_id,ble_name);
  if(length<0 || length>=sizeof(json)) abort();
#else
  snprintf(json, sizeof(json),
           "{\"device_id\":\"%s\",\"short_id\":\"%s\",\"name\":\"%s\"}",
           device_id, short_id, ble_name);
#endif
  initialized = true;
}

const char* identity_device_id() {
  identity_init();
  return device_id;
}

const char* identity_short_id() {
  identity_init();
  return short_id;
}

const char* identity_ble_name() {
  identity_init();
  return ble_name;
}

const char* identity_json() {
  identity_init();
  return json;
}
