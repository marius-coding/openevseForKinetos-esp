# Detailed Comparison: OpenEVSE vs Kinetos RAPI Communication (AI generated)

This document compares the RAPI protocol communication sequences between OpenEVSE and Kinetos charging stations, based on annotated serial sniff logs captured during startup and charging phases. The analysis covers command structure, configuration, status reporting, and energy data exchange.

---

## 1. Overview

- **RAPI Protocol**: Both devices use the RAPI protocol for serial communication between the controller and WiFi gateway. Commands are exchanged over RX/TX lines at 115200 baud.
- **Log Sources**:
  - **OpenEVSE**: `openevse_idle.sniff.commented`, `openevse_400W.sniff.commented`
  - **Kinetos**: `kinetos_startup.sniff.commented`, `kinetos_400w.sniff.commented`

---

## 2. Boot/Startup Sequence

| Step | OpenEVSE | Kinetos |
|------|----------|---------|
| 1 | AT: Query status/version | AT: Query status/version |
| 2 | GV: Get firmware version | GV: Get firmware version |
| 3 | AB: Device identification | AB: Device identification |
| 4 | GT: Get time/timer info | GT: Get time/timer info |
| 5 | NK: Keepalive/heartbeat | NK: Keepalive/heartbeat |
| 6 | GF/GE: Get features/energy | GF/GE: Get features/energy |
| 7 | GC: Get configuration | GC: Get configuration |
| 8 | GA/GI: Get auth/ID info | GA/GI: Get auth/ID info |
| 9 | SY/GS/GP: Set/get system params | SY/GS/GP: Set/get system params |

**Notes:**
- Both devices query status, firmware, and identification early in the sequence.
- Kinetos includes additional user info (GU) and more frequent timer/voltage set commands (SV, T1).
- OpenEVSE uses more explicit authentication and configuration queries (GA, GI).

---

## 3. Configuration and Status Reporting

### OpenEVSE
- **GC**: Get configuration (frequent)
- **SC**: Set configuration (slot 0, value V)
- **OK**: Status/feature response (e.g., ['6', '16', '6', '16'])
- **NK**: Keepalive/heartbeat
- **FP**: Display info (hostname, IP, charging status, energy, temp)

### Kinetos
- **GC**: Get configuration
- **GU**: Get user info
- **SV**: Set voltage (likely)
- **T0/T1/T2**: Set timer/state
- **FP**: Display info (hostname, IP, charging status, energy, temp)
- **GG**: Get grid/energy info
- **SL**: Set limit/state

**Notes:**
- OpenEVSE cycles configuration and status commands in a tight loop, especially during charging.
- Kinetos interleaves voltage/timer commands with status and energy queries, reflecting more granular control.

---

## 4. Charging Phase Communication

### OpenEVSE (`openevse_400W.sniff.commented`)
- Repeated sequence:
  - GC (Get config)
  - SC (Set config)
  - OK (Status response)
  - NK (Keepalive)
  - FP (Charging status, energy, temp)
- Status/feature response remains consistent (['6', '16', '6', '16'])
- Charging status and energy values update (e.g., 'Charging…1.61A', 'Energy…13.2Wh')

### Kinetos (`kinetos_400w.sniff.commented`)
- Repeated sequence:
  - SV (Set voltage)
  - T0/T1/T2 (Set timer/state)
  - GG (Get grid/energy info)
  - FP (Charging status, energy, temp)
  - GU (Get user info)
- Grid/energy and timer responses update (e.g., ['1656', '227700'], ['320400', '89'])
- Charging status and energy values update (e.g., 'Charging…0.37kW', 'Energy…89.0Wh')

---

## 5. Command Structure and Arguments

| Command | OpenEVSE Example | Kinetos Example | Purpose |
|---------|------------------|-----------------|---------|
| AT      | AT 00 00 0 0200  | AT 00 00 0 0200 | Query status/version |
| GV      | GV               | GV              | Get firmware version |
| AB      | AB 00 E532_L-8.2.0 | AB 00 E532_L-8.2.0 | Device identification |
| GC      | GC               | GC              | Get configuration |
| SC      | SC 0 V           | (not present)   | Set configuration |
| SV      | (not present)    | SV 228800       | Set voltage |
| T0/T1/T2| (not present)    | T0 0 0 0 / T1 89| Set timer/state |
| GG      | (not present)    | GG              | Get grid/energy info |
| FP      | FP 0 0 Hostname: | FP 0 0 Hostname:| Display info |
| OK      | OK 6 16 6 16     | OK 6 16 16 16   | Status/feature response |
| NK      | NK               | NK              | Keepalive/heartbeat |

---

## 6. Energy and Status Data

- **OpenEVSE**:
  - Reports charging current (e.g., 'Charging…1.61A')
  - Reports energy counters (e.g., 'Energy…13.2Wh', 'Lifetime…15Wh')
  - Reports temperature (e.g., 'EVSE Temp…27.7C')
- **Kinetos**:
  - Reports charging power (e.g., 'Charging…0.37kW')
  - Reports energy counters (e.g., 'Energy…89.0Wh', 'Lifetime…0kWh')
  - Reports temperature (e.g., 'EVSE Temp…29.0C')
  - Reports grid/energy values (e.g., ['1656', '227700'])

---

## 7. Differences and Similarities

### Similarities
- Both use RAPI commands for status, configuration, and energy reporting.
- Both display device info (hostname, IP, charging status, energy, temp).
- Both use keepalive/heartbeat (NK) and generic OK responses.

### Differences
- **OpenEVSE**:
  - Emphasizes configuration cycling (GC/SC) and status reporting.
  - Less direct control over voltage/timer.
  - Energy reporting in Wh, current in A.
- **Kinetos**:
  - Actively sets voltage and timer/state (SV, T0/T1/T2).
  - Uses grid/energy info (GG) and user info (GU).
  - Energy reporting in Wh, power in kW.
  - More granular control and feedback in charging phase.

---

## 8. Conclusion

- **OpenEVSE**: Prioritizes configuration and status polling, with frequent queries and updates. Suitable for environments where configuration/state changes are less dynamic.
- **Kinetos**: Implements more active control over charging parameters, voltage, and timers, enabling dynamic energy management and detailed feedback.
- **Interoperability**: Both devices share core RAPI command structure, but differ in control philosophy and data granularity. Understanding these differences is key for integration, diagnostics, and protocol extension.

---

## 9. References
- Annotated logs: See `.sniff.commented` files in workspace
- RAPI protocol documentation: [OpenEVSE API Docs](https://openevse.stoplight.io/docs/openevse-wifi-v4/)
- Device manuals: See `docs/` folder

## 10. Human: Additional thoughts

Apparently, the Kinetos firmware reads the voltage from the energy meter, sends it to the LGT8F328P clone, and then reads it back from the LGT8F328P. 

The openEVSE trace does not contain any get voltage commands because the firmware has already been modified to read the voltage from the energy meter instead of the rapi bus.

The Kinetos LGT8F328P firmware has some compatibility with the OpenEVSe esp firmware, but the behavior is somewhat peculiar. When the charging request has been changed via the web UI, a CP signal from the vehicle (release 1,3K resistor) will not turn off charging. The Kinetos firmware (esp + LGT8F328P) is also unable to reliably process the CP resistor signal. There seems to be a bug in the Kinetos LGT8F328P Firmware.