# OpenEVSE WiFi for ESP32

## Fork for Kinetos wallbox

- This repository is a fork of OpenEVSE WiFi for ESP32 adapted to run on the Kinetos AC wallbox hardware.
- Kinetos (the company) has gone out of business; this fork exists to keep existing units usable.
- Hardware similarities and differences:
  - EVSE controller MCU: LGT8F328P (ATmega328P-compatible) instead of ATmega328P
  - Energy/power metering: external Modbus meter connected to the WT32-ETH01 module (ESP32 with Ethernet), rather than to the EVSE controller
- Motivation: the original Kinetos firmware exhibited issues (e.g. sometimes failing to turn off even after the Control Pilot (CP) signal was released). This project adapts the OpenEVSE stack to the Kinetos hardware and addresses those problems.
- This project is community-maintained and not affiliated with Kinetos.

### Kinetos power meter drivers

Kinetos hardware variants ship with an external Modbus power meter connected to the ESP32 (WT32‑ETH01). This fork supports two meter drivers. Enable exactly one at build time:

- SDM630MCT driver (default for SDM630‑class meters)
  - Source: src/sdm630mct.h
  - Build flag: `ENABLE_SDM630MCT`
  - Reads IEEE‑754 floats using Modbus FC=0x04 from the meter’s standard register map and aggregates 3‑phase values.
  - EVSE monitor uses these readings to update voltage, current and power.

- Kinetos power meter driver (for Kinetos‑specific meters)
  - Source: src/kinetos_meter.h
  - Build flag: `ENABLE_KINETOS_METER`
  - Reads raw 32‑bit values (two input registers) via Modbus FC=0x04 at:
    - 0x0100 → Voltage
    - 0x0106 → Current
    - 0x010E → Power
  - Scaling (applied in driver):
    - Voltage = value / 10.0
    - Current = value / 1000.0
    - Power   = value / 10.0

Driver selection and behavior
- Set the build flag in your PlatformIO environment (only one of the two):
  - `-DENABLE_SDM630MCT` for SDM630‑class meters
  - `-DENABLE_KINETOS_METER` for Kinetos meters
- When either external meter driver is enabled, the EVSE monitor loop reads the meter each cycle and publishes a single event containing top‑level keys: `voltage`, `amp`, `power`.
  - These are pushed to the web UI over WebSocket and published to MQTT as `<mqtt_topic>/voltage`, `<mqtt_topic>/amp`, `<mqtt_topic>/power`.
- If neither flag is defined, the firmware falls back to reading current/voltage from the OpenEVSE controller via RAPI.

Hardware notes
- Default serial for the external meter is UART2 (ESP32 Serial2) at 9600 baud, 8N2 framing. An optional RS485 DE/RE control pin can be configured in the drivers if your transceiver requires it.


> **_NOTE:_** Breaking change! This release recommends a minimum of [7.1.3](https://github.com/OpenEVSE/open_evse/releases) of the OpenEVSE firmware, features including Solar Divert and push button menus may not behave as expected on older firmware.

- *For the older WiFi V2.x ESP8266 version (pre June 2020), see the [v2 firmware repository](https://github.com/openevse/ESP8266_WiFi_v2.x/)*

- **For latest API documentation see the new [Spotlight.io OpenEVSE WiFi documentation page](https://openevse.stoplight.io/docs/openevse-wifi-v4/ZG9jOjQyMjE5ODI-open-evse-wi-fi-esp-32-gateway-v4)**

![main](docs/main2.png)

The WiFi gateway uses an **ESP32** which communicates with the OpenEVSE controller via serial RAPI API. The web UI is served directly from the ESP32 web server and can be controlled via a connected device on the local network.

**This FW also supports wired Ethernet connection using [ESP32 Gateway](docs/wired-ethernet.md)**


***

## Contents

<!-- toc -->

- [Features](#features)
- [Requirements](#requirements)
- [User Guide](docs/user-guide.md)
- [Firmware Development Guide](docs/developer-guide.md)
- [API](https://openevse.stoplight.io/docs/openevse-wifi-v4/)
- [About](#about)
- [Licence](#licence)

<!-- tocstop -->

## Features

- Web UI to view & control all OpenEVSE functions
  - Start / pause
  - Scheduler
  - Session & system limits (time, energy, soc, range)
  - Adjust charging current

- MQTT status & control
- Log to Emoncms server e.g [data.openevse.com](https://data.openevse.com) or [emoncms.org](https://emoncms.org)
- 'Eco' mode: automatically adjust charging current based on availability of power from solar PV or grid export
- Shaper: throttle current to prevent overflowing main power capacity 
- OCPP V1.6 (beta)
- [Home Assistant Integration (beta)](https://github.com/firstof9/openevse)

## Requirements

### OpenEVSE / EmonEVSE charging station

- Purchase via: [OpenEVSE Store](https://store.openevse.com)
- OpenEVSE FW [V7.1.3 recommended](https://github.com/OpenEVSE/open_evse/releases)
- All new OpenEVSE units are shipped with V7.1.3 pre-loaded (April 2021 onwards)

### ESP32 WiFi Module

- **Note: WiFi module is included as standard in most OpenEVSE units**
- Purchase via: [OpenEVSE Store (USA/Canda)](https://store.openevse.com/collections/frontpage/products/openevse-wifi-kit) | [OpenEnergyMonitor (UK / EU)](https://shop.openenergymonitor.com/openevse-wifi-gateway/)
- See [OpenEVSE WiFi setup guide](https://openevse.dozuki.com/Guide/WiFi+-+Join+Network/29) for basic instructions

***

## About

Collaboration of [OpenEnegyMonitor](http://openenergymonitor.org) and [OpenEVSE](https://openevse.com).

Contributions by:

- @glynhudson
- @chris1howell
- @trystanlea
- @jeremypoulter
- @sandeen
- @lincomatic
- @joverbee
- @matth-x (OCPP)
- @kipk

## Licence

GNU General Public License (GPL) V3
