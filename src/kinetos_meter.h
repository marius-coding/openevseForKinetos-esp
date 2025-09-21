#ifndef KINETOS_METER_H
#define KINETOS_METER_H

#include <Arduino.h>

/*
  Kinetos power meter Modbus-RTU driver (minimal)

  - Designed for ESP32 UART (default Serial2) with optional RS485 DE/RE control
  - Reads 32-bit register values via Modbus function 0x04 (Input Registers)
  - Provides simple getters for Voltage, Current and Power using raw 32-bit values

  Scaling (per request):
    - Voltage = readU32Raw(0x0100) / 10.0
    - Current = readU32Raw(0x0106) / 1000.0
    - Power   = readU32Raw(0x010e) / 10.0

  No error checking is performed in readU32Raw, by design.
*/
class KinetosMeter {
public:
  explicit KinetosMeter(HardwareSerial &serial = Serial2,
                        uint8_t slave_address = 0x01,
                        int8_t de_re_pin = -1)
      : _serial(serial), _addr(slave_address), _de_re_pin(de_re_pin),
        _timeout_ms(200), _inter_frame_delay_us(3500) {}

  void begin(uint32_t baud = 9600, bool init_serial = false) {
    if (_de_re_pin >= 0) {
      pinMode(_de_re_pin, OUTPUT);
      digitalWrite(_de_re_pin, LOW); // receive by default
    }
    if (init_serial) {
      _serial.begin(baud, SERIAL_8N2);
    }
  }

  void setTimeout(uint16_t timeout_ms) { _timeout_ms = timeout_ms; }
  void setInterFrameDelay(uint32_t micros_delay) { _inter_frame_delay_us = micros_delay; }
  void setAddress(uint8_t addr) { _addr = addr; }

  // Raw 32-bit read (2 input registers). No error checking.
  uint32_t readU32Raw(uint16_t reg) {
    uint8_t req[8];
    req[0] = _addr;
    req[1] = FC_READ_INPUT_REGISTERS;
    req[2] = (uint8_t)(reg >> 8);
    req[3] = (uint8_t)(reg & 0xFF);
    req[4] = 0x00;
    req[5] = 0x02; // quantity of registers = 2
    uint16_t crc = crc16_modbus(req, 6);
    req[6] = (uint8_t)(crc & 0xFF);
    req[7] = (uint8_t)((crc >> 8) & 0xFF);

    flushInput();

    if (_de_re_pin >= 0) { digitalWrite(_de_re_pin, HIGH); delayMicroseconds(10); }
    (void)_serial.write(req, sizeof(req));
    _serial.flush();
    if (_de_re_pin >= 0) { delayMicroseconds(10); digitalWrite(_de_re_pin, LOW); }

    delayMicroseconds(_inter_frame_delay_us);

    uint8_t resp[9] = {0};
    size_t got = 0;
    unsigned long start = millis();
    while ((millis() - start) < _timeout_ms && got < sizeof(resp)) {
      if (_serial.available()) resp[got++] = (uint8_t)_serial.read();
      else delay(1);
    }

    uint32_t val = ((uint32_t)resp[3] << 24) |
                   ((uint32_t)resp[4] << 16) |
                   ((uint32_t)resp[5] << 8)  |
                   ((uint32_t)resp[6]);
    return val;
  }

  // Convenience getters with scaling
  double getVoltage() { return (double)readU32Raw(0x0100) / 10.0; }
  double getCurrent() { return (double)readU32Raw(0x0106) / 1000.0; }
  double getPower()   { return (double)readU32Raw(0x010e) / 10.0; }

private:
  static constexpr uint8_t FC_READ_INPUT_REGISTERS = 0x04;

  HardwareSerial &_serial;
  uint8_t _addr;
  int8_t _de_re_pin;
  uint16_t _timeout_ms;
  uint32_t _inter_frame_delay_us;

  static uint16_t crc16_modbus(const uint8_t *buf, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t pos = 0; pos < len; pos++) {
      crc ^= (uint16_t)buf[pos];
      for (int i = 0; i < 8; i++) {
        if (crc & 0x0001) { crc >>= 1; crc ^= 0xA001; }
        else { crc >>= 1; }
      }
    }
    return crc;
  }

  void flushInput() {
    unsigned long t0 = micros();
    while (_serial.available()) {
      (void)_serial.read();
      if ((micros() - t0) > 2000) break;
    }
  }
};

#endif // KINETOS_METER_H
