#include "config.h"
#ifdef CODEXMETER_BOARD_BALL
#include <Wire.h>
#include <Preferences.h>
#include "power.h"
#include "imu.h"
#include "touch_input.h"
#include "ui.h"
#include "device_log.h"

namespace {
Preferences rotation_store;
uint8_t rotation = 0;
bool rotation_store_ok = false;
volatile bool touch_irq = false;
uint32_t irq_count = 0, errors = 0, samples = 0;
bool ready = false, down = false, cancelled = false;
int start_x, start_y, end_x, end_y;
uint32_t started, last_sample, last_poll;
uint8_t contact_rotation;
void ARDUINO_ISR_ATTR touch_interrupt() { touch_irq = true; }
bool read_touch(uint8_t reg, uint8_t* data, size_t size) {
  Wire.beginTransmission(0x15); Wire.write(reg);
  if (Wire.endTransmission(false) || Wire.requestFrom(uint8_t(0x15),uint8_t(size)) != size) { ++errors; return false; }
  for(size_t i=0;i<size;++i) data[i]=Wire.read();
  return true;
}
}
void power_init() { Wire.begin(11,7,100000); Wire.setTimeOut(30); }
void power_tick() {}
void power_set_display_active(bool) {}
bool power_take_state_changed() { return false; }
int power_battery_percent() { return -1; }
bool power_is_charging() { return false; }
void power_refresh_and_log() { device_logf("INFO","Ball power source/charging/battery presence unavailable"); }
PowerKeyEvent power_take_key_event() { return PowerKeyEvent::None; }
bool imu_init() {
  rotation_store_ok=rotation_store.begin("ball_display",false);
  if(rotation_store_ok) rotation=rotation_store.getUChar("rotation",0)&3;
  return false;
}
void imu_tick() {}
void imu_set_display_active(bool) {}
bool imu_available() { return false; }
bool imu_auto_rotation_enabled() { return false; }
void imu_set_auto_rotation(bool) {}
bool imu_set_rotation_quadrant(uint8_t value) {
  if(value>3) return false;
  if(value!=rotation) { rotation=value; if(rotation_store_ok) rotation_store.putUChar("rotation",value); }
  return true;
}
uint8_t imu_rotation_quadrant() { return rotation; }
bool imu_last_sample(float*,float*,float*) { return false; }
const char* imu_rotation_label(uint8_t value) { static const char* labels[]={"0","90","180","270"}; return labels[value&3]; }
void imu_print_status(Stream& out) { out.printf("ROTATION manual=%u sensor=none\n",rotation*90); }
void touch_input_init() {
  pinMode(6,OUTPUT);digitalWrite(6,LOW);delay(30);digitalWrite(6,HIGH);delay(100);
  Wire.beginTransmission(0x15);Wire.write(0xfe);Wire.write(1);
  bool configured=Wire.endTransmission()==0;
  uint8_t id=0,sleep=0;
  ready=configured && read_touch(0xa7,&id,1) && id==0xb6 && read_touch(0xfe,&sleep,1) && sleep==1;
  pinMode(12,INPUT_PULLUP);attachInterrupt(digitalPinToInterrupt(12),touch_interrupt,FALLING);
  device_logf(ready?"INFO":"ERROR","CST816D ready=%d id=%02x no_sleep=%u",ready,id,sleep);
}
void touch_input_tick(bool active) {
  if(!ready) return;
  uint32_t now=millis();
  if(!active) { down=false;cancelled=true;return; }
  if(!touch_irq && now-last_poll<10) return;
  if(touch_irq) { ++irq_count;touch_irq=false; }
  last_poll=now;uint8_t data[6];
  if(!read_touch(1,data,6)) { if(down) cancelled=true; return; }
  int contacts=data[1]&15;
  if(contacts==1) {
    int x=((data[2]&15)<<8)|data[3],y=((data[4]&15)<<8)|data[5];
    if(x>=240 || y>=240) { cancelled=true;return; }
    int px=x,py=y;
    switch(rotation) {case 1:x=py;y=239-px;break;case 2:x=239-px;y=239-py;break;case 3:x=239-py;y=px;break;}
    if(!down) { down=true;cancelled=false;start_x=x;start_y=y;started=now;contact_rotation=rotation; }
    if(rotation!=contact_rotation) cancelled=true;
    end_x=x;end_y=y;last_sample=now;++samples;
  } else if(contacts>1) { cancelled=true; }
  else if(down) {
    down=false;
    int dx=end_x-start_x,dy=end_y-start_y;
    if(!cancelled && rotation==contact_rotation && now-started<=1000 && abs(dx)>=40 && abs(dx)*2>=abs(dy)*3)
      ui_touch_gesture(dx,dy,end_x,end_y,false);
    else if(!cancelled && now-started<700 && abs(dx)<18 && abs(dy)<18)
      ui_touch_gesture(0,0,end_x,end_y,true);
  }
}
void touch_input_diagnostics() { Serial.printf("TOUCH ready=%d samples=%lu irq=%lu errors=%lu x=%d y=%d\n",ready,samples,irq_count,errors,end_x,end_y); }
#endif
