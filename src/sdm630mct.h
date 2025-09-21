#ifndef SDM630MCT_H
#define SDM630MCT_H

#include <Arduino.h>

/*
  SDM630MCT Modbus-RTU driver (minimal)

  - Designed for ESP32 WT32-ETH01 using UART0 (Serial) on TXD0/RXD0 by default
  - Reads floating-point measurements via Modbus function 0x04 (Input Registers)
  - Provides getters for aggregate voltage, current and active power

  Notes
  - SDM630MCT default: 9600 8N1, slave address 1
  - Measured values are exposed as IEEE-754 float across 2 registers
  - This driver reads per-phase values and aggregates:
      voltage = average(L1-N, L2-N, L3-N)
      current = sum(I1 + I2 + I3)
      power   = sum(P1 + P2 + P3) active power (W)
  - Optional RS485 DE/RE control pin supported if a transceiver is used

  Integration
  - The constructor defaults to Serial (UART0). If Serial is already in use
    elsewhere, pass a different HardwareSerial instance.
  - begin(baud, init_serial=false): set init_serial=true only if you want this
    driver to configure the UART. If another module handles Serial, leave false.

  Register map (commonly used for SDM630MCT; values are Big-Endian):
    0x0000 Voltage L1-N
    0x0002 Voltage L2-N
    0x0004 Voltage L3-N
    0x0006 Current L1
    0x0008 Current L2
    0x000A Current L3
    0x0034 Active Power L1
    0x0036 Active Power L2
    0x0038 Active Power L3
*/

class SDM630MCT {
 public:
  explicit SDM630MCT(HardwareSerial &serial = Serial,
                     uint8_t slave_address = 0x01,
                     int8_t de_re_pin = -1)
      : _serial(serial),
        _addr(slave_address),
        _de_re_pin(de_re_pin),
        _timeout_ms(200),
        _inter_frame_delay_us(3500) {} // ~3.5 char times at 9600 baud

  // If init_serial is true, this will call serial.begin(baud, SERIAL_8N1)
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

  // Aggregate getters (3-phase):
  // voltage = average of L1/L2/L3 phase-to-neutral voltages
  bool getVoltage(float &voltage) {
    float v1, v2, v3;
    if (!readFloat(REG_VOLTAGE_L1N, v1)) return false;
    if (!readFloat(REG_VOLTAGE_L2N, v2)) return false;
    if (!readFloat(REG_VOLTAGE_L3N, v3)) return false;
    voltage = (v1 + v2 + v3) / 3.0f;
    return true;
  }

  // current = sum of L1/L2/L3 currents
  bool getCurrent(float &current) {
    float i1, i2, i3;
    if (!readFloat(REG_CURRENT_L1, i1)) return false;
    if (!readFloat(REG_CURRENT_L2, i2)) return false;
    if (!readFloat(REG_CURRENT_L3, i3)) return false;
    current = (i1 + i2 + i3);
    return true;
  }

  // power = sum of L1/L2/L3 active power (W)
  bool getPower(float &power) {
    float p1, p2, p3;
    if (!readFloat(REG_POWER_L1, p1)) return false;
    if (!readFloat(REG_POWER_L2, p2)) return false;
    if (!readFloat(REG_POWER_L3, p3)) return false;
    power = (p1 + p2 + p3);
    return true;
  }

  // Optional per-phase getters
  bool getVoltageL1(float &v) { return readFloat(REG_VOLTAGE_L1N, v); }
  bool getVoltageL2(float &v) { return readFloat(REG_VOLTAGE_L2N, v); }
  bool getVoltageL3(float &v) { return readFloat(REG_VOLTAGE_L3N, v); }

  bool getCurrentL1(float &i) { return readFloat(REG_CURRENT_L1, i); }
  bool getCurrentL2(float &i) { return readFloat(REG_CURRENT_L2, i); }
  bool getCurrentL3(float &i) { return readFloat(REG_CURRENT_L3, i); }

  bool getPowerL1(float &p) { return readFloat(REG_POWER_L1, p); }
  bool getPowerL2(float &p) { return readFloat(REG_POWER_L2, p); }
  bool getPowerL3(float &p) { return readFloat(REG_POWER_L3, p); }

  private:
  // SDM630 register addresses (2-register IEEE-754 each)
  static constexpr uint16_t REG_VOLTAGE_L1N = 0x0000;
  static constexpr uint16_t REG_VOLTAGE_L2N = 0x0002;
  static constexpr uint16_t REG_VOLTAGE_L3N = 0x0004;
  static constexpr uint16_t REG_CURRENT_L1  = 0x0006;
  static constexpr uint16_t REG_CURRENT_L2  = 0x0008;
  static constexpr uint16_t REG_CURRENT_L3  = 0x000A;
  static constexpr uint16_t REG_POWER_L1    = 0x0034;
  static constexpr uint16_t REG_POWER_L2    = 0x0036;
  static constexpr uint16_t REG_POWER_L3    = 0x0038;

  // Modbus function code for Input Registers
  static constexpr uint8_t FC_READ_INPUT_REGISTERS = 0x04;

  HardwareSerial &_serial;
  uint8_t _addr;
  int8_t _de_re_pin; // RS485 DE/RE control, -1 if not used
  uint16_t _timeout_ms;
  uint32_t _inter_frame_delay_us;

  // Read a single IEEE-754 float (2 registers) from Modbus input registers
  bool readFloat(uint16_t reg, float &value) {
    uint8_t req[8];
    req[0] = _addr;
    req[1] = FC_READ_INPUT_REGISTERS;
    req[2] = (uint8_t)(reg >> 8);
    req[3] = (uint8_t)(reg & 0xFF);
    req[4] = 0x00;
    req[5] = 0x02; // quantity of registers = 2 (float)
    uint16_t crc = crc16_modbus(req, 6);
    req[6] = (uint8_t)(crc & 0xFF);      // CRC lo
    req[7] = (uint8_t)((crc >> 8) & 0xFF); // CRC hi

    flushInput();

    // TX enable if RS485
    if (_de_re_pin >= 0) {
      digitalWrite(_de_re_pin, HIGH);
      delayMicroseconds(10);
    }

    size_t written = _serial.write(req, sizeof(req));
    _serial.flush(); // wait for TX done

    // Back to RX
    if (_de_re_pin >= 0) {
      delayMicroseconds(10);
      digitalWrite(_de_re_pin, LOW);
    }

    // Inter-frame delay to allow slave to respond
    delayMicroseconds(_inter_frame_delay_us);

    // Expecting 9 bytes: addr, func, byteCount(=4), data(4), CRC(2)
    const size_t expected = 9;
    uint8_t resp[expected];
    unsigned long start = millis();
    size_t got = 0;
    while ((millis() - start) < _timeout_ms && got < expected) {
      if (_serial.available()) {
        resp[got++] = (uint8_t)_serial.read();
      } else {
        delay(1);
      }
    }

    if (written != sizeof(req)) return false;
    if (got != expected) return false;

    // Basic header checks
    if (resp[0] != _addr) return false;
    if (resp[1] != FC_READ_INPUT_REGISTERS) return false;
    if (resp[2] != 0x04) return false; // byte count must be 4

    // CRC check
    uint16_t rx_crc = (uint16_t)resp[7] | ((uint16_t)resp[8] << 8);
    uint16_t calc_crc = crc16_modbus(resp, expected - 2);
    if (rx_crc != calc_crc) return false;

    // Data bytes: resp[3..6] (big-endian IEEE-754)
    value = bytesToFloatBE(&resp[3]);

    // NaN guard
    if (isnan(value) || isinf(value)) return false;

    return true;
  }

  static float bytesToFloatBE(const uint8_t *p) {
    // Big-endian 32-bit float: b0 b1 b2 b3 -> (b0<<24 | b1<<16 | b2<<8 | b3)
    uint32_t u = ((uint32_t)p[0] << 24) |
                 ((uint32_t)p[1] << 16) |
                 ((uint32_t)p[2] << 8)  |
                 ((uint32_t)p[3]);
    float f;
    memcpy(&f, &u, sizeof(float));
    return f;
  }

  static uint16_t crc16_modbus(const uint8_t *buf, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t pos = 0; pos < len; pos++) {
      crc ^= (uint16_t)buf[pos];
      for (int i = 0; i < 8; i++) {
        if (crc & 0x0001) {
          crc >>= 1;
          crc ^= 0xA001;
        } else {
          crc >>= 1;
        }
      }
    }
    return crc;
  }

  void flushInput() {
    // purge any stale bytes
    unsigned long t0 = micros();
    while (_serial.available()) {
      (void)_serial.read();
      if ((micros() - t0) > 2000) break; // don't block forever
    }
  }
};

#endif // SDM630MCT_H
