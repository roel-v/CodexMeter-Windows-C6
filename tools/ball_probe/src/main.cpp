#include <Arduino.h>
#include <Wire.h>
#include <Arduino_GFX_Library.h>
#include <NimBLEDevice.h>
#include <esp_heap_caps.h>

constexpr uint16_t BLACK=0x0000, WHITE=0xffff, RED=0xf800, GREEN=0x07e0, BLUE=0x001f;
// Dedicated temporary probe: no CodexMeter service, Wi-Fi or credentials.
Arduino_ESP32SPI bus(47, 5, 4, 2, -1);
Arduino_GC9A01 lcd(&bus, 38, 0, true);
TwoWire audioBus(1);
bool memoryOK = false;
uint8_t touchId = 0xff;
unsigned touchEvents = 0, buttonEvents = 0, readErrors = 0;
volatile unsigned irqCount = 0;
volatile bool touchPending = false;
uint8_t sleepDisabled = 0xff;
void ARDUINO_ISR_ATTR touchIRQ() { ++irqCount; touchPending = true; }
const char* serviceId = "c631f467-6768-4000-8000-000000000001";
const char* statusId = "c631f467-6768-4000-8000-000000000002";
NimBLECharacteristic* statusChar;

bool readTouch(uint8_t reg, uint8_t* data, size_t count) {
  Wire.beginTransmission(0x15); Wire.write(reg);
  if (Wire.endTransmission(false)) return false;
  if (Wire.requestFrom(uint8_t(0x15), uint8_t(count)) != count) return false;
  for (size_t i=0; i<count; ++i) data[i]=Wire.read();
  return true;
}
void scan(TwoWire& wire, const char* name) {
  for (int address=8; address<120; ++address) {
    wire.beginTransmission(address);
    if (!wire.endTransmission()) Serial.printf("I2C %s address=0x%02x\n", name, address);
  }
}
void setup() {
  Serial.begin(115200); delay(1800);
  pinMode(0, INPUT_PULLUP); pinMode(12, INPUT_PULLUP);
  pinMode(42, OUTPUT); digitalWrite(42, HIGH); // inverted backlight off
  pinMode(6, OUTPUT); digitalWrite(6, LOW); delay(20); digitalWrite(6,HIGH); delay(100);
  Wire.begin(11,7,100000); Wire.setTimeOut(30);
  audioBus.begin(15,14,100000); audioBus.setTimeOut(30);
  scan(Wire,"touch"); scan(audioBus,"audio");
  readTouch(0xa7,&touchId,1);
  // Match SensorLib CST816D initialization: wake/reset before disabling auto sleep.
  digitalWrite(6,LOW); delay(30); digitalWrite(6,HIGH); delay(100);
  Wire.beginTransmission(0x15); Wire.write(0xfe); Wire.write(0x01);
  unsigned sleepWrite=Wire.endTransmission();
  readTouch(0xfe,&sleepDisabled,1);
  attachInterrupt(digitalPinToInterrupt(12),touchIRQ,FALLING);
  Serial.printf("TOUCH_CONFIG sleep_write=%u sleep_read=%u\n",sleepWrite,sleepDisabled);
  size_t bytes=4*1024*1024;
  auto* memory=static_cast<uint32_t*>(heap_caps_malloc(bytes,MALLOC_CAP_SPIRAM));
  if(memory) {
    for(size_t i=0;i<bytes/4;++i) memory[i]=uint32_t(i)^0xa55a3cc3;
    memoryOK=true;
    for(size_t i=0;i<bytes/4;++i) if(memory[i]!=(uint32_t(i)^0xa55a3cc3)) {memoryOK=false;break;}
    free(memory);
  }
  bool lcdOK=lcd.begin(40000000); lcd.invertDisplay(false); // ips=true maps false to the panel INVON command
  lcd.fillScreen(BLACK);
  lcd.drawCircle(120,120,116,WHITE);
  lcd.setTextSize(2); lcd.setTextColor(WHITE); lcd.setCursor(60,34); lcd.print("PROBE V3");
  lcd.fillRect(30,68,60,32,RED); lcd.fillRect(90,68,60,32,GREEN); lcd.fillRect(150,68,60,32,BLUE);
  lcd.setTextSize(1); lcd.setCursor(50,112); lcd.print("Touch / swipe to test");
  lcd.setCursor(50,126); lcd.print("Short BOOT press = count");
  lcd.setCursor(58,202); lcd.print("Temporary diagnostic");
  analogWrite(42,160); // modest brightness, inverted
  analogReadResolution(12); analogSetPinAttenuation(1,ADC_11db);
  NimBLEDevice::init("BallProbe-F46768");
  auto* server=NimBLEDevice::createServer(); server->advertiseOnDisconnect(true);
  auto* service=server->createService(serviceId);
  statusChar=service->createCharacteristic(statusId,NIMBLE_PROPERTY::READ);
  service->start(); auto* adv=NimBLEDevice::getAdvertising();
  adv->addServiceUUID(serviceId); adv->enableScanResponse(true); adv->setName("BallProbe-F46768"); adv->start();
  Serial.printf("START lcd_init=%d flash=%u psram=%u memory_4MB=%d touch_id=0x%02x\n",lcdOK,ESP.getFlashChipSize(),ESP.getPsramSize(),memoryOK,touchId);
}
void loop() {
  static unsigned long last=0, lastTouch=0;
  static bool buttonWas=false;
  bool button=!digitalRead(0);
  if(button && !buttonWas) {++buttonEvents; Serial.printf("BUTTON count=%u\n",buttonEvents);}
  buttonWas=button;
  if(touchPending || millis()-lastTouch>10) {
    lastTouch=millis(); touchPending=false; uint8_t data[6];
    bool readOK=readTouch(0x01,data,6);
    if(!readOK) ++readErrors;
    if(readOK && (data[1]&0x0f)==1) {
      int x=((data[2]&0x0f)<<8)|data[3], y=((data[4]&0x0f)<<8)|data[5];
      ++touchEvents; Serial.printf("TOUCH x=%d y=%d gesture=%u\n",x,y,data[0]);
      lcd.fillRect(45,145,155,12,BLACK); lcd.setCursor(45,145); lcd.printf("Touch: %3d, %3d",x,y);
    }
  }
  if(millis()-last>2000) {
    last=millis(); unsigned mv=analogReadMilliVolts(1)*2;
    char status[220]; snprintf(status,sizeof(status),"{\"uptime_ms\":%lu,\"flash\":%u,\"psram\":%u,\"memory_ok\":%s,\"touch_id\":%u,\"adc_mv_x2\":%u,\"touch_events\":%u,\"button_events\":%u}",millis(),ESP.getFlashChipSize(),ESP.getPsramSize(),memoryOK?"true":"false",touchId,mv,touchEvents,buttonEvents);
    Serial.println(status); statusChar->setValue(status);
    Serial.printf("TOUCH_DIAG irq=%u errors=%u sleep=%u pin=%d\n",irqCount,readErrors,sleepDisabled,digitalRead(12));
    lcd.fillRect(45,190,155,9,BLACK); lcd.setCursor(45,190); lcd.printf("IRQ:%u Err:%u",irqCount,readErrors);
    lcd.fillRect(45,165,155,25,BLACK); lcd.setCursor(45,165); lcd.printf("ADC x2: %u mV",mv);
    lcd.setCursor(45,178); lcd.printf("BOOT: %u  RAM: %s",buttonEvents,memoryOK?"PASS":"FAIL");
  }
  delay(5);
}
