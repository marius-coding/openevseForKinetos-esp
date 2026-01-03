# Bug Report: LED Color Override Not Working for "ready" and "charging" States

## Summary
LED color override feature does not apply color/brightness changes when device is in `ready` or `charging` states. The override works correctly for `waiting` state and when using `all` states.

## Environment
- **Firmware Version**: local_feature/led-color-override-feature_caf802bd
- **Build Date**: 2026-01-03T14:13:59Z
- **Build Environment**: kinetos
- **Device**: openevse2.local (192.168.0.149)
- **Hardware**: ESP32r1 2 core WiFi BLE BT

## Steps to Reproduce

### Test 1: Setting override for "charging" state (FAILS)
**HTTP API:**
```bash
curl -X POST http://openevse2.local/led -H "Content-Type: application/json" \
  -d '{"state":"charging","color":"#00FF00","brightness":255,"timeout":1}'
```

**MQTT API:**
```bash
mosquitto_pub -h localhost -t "openevse/led/set" \
  -m '{"state":"charging","color":"#00FF00","brightness":255,"timeout":1}'
```

**Result**: API returns 200 OK with `{"msg":"done"}`, but LED color/brightness does not change when device enters charging state.

### Test 2: Setting override for "ready" state (FAILS)
**HTTP API:**
```bash
curl -X POST http://openevse2.local/led -H "Content-Type: application/json" \
  -d '{"state":"ready","color":"#0000FF","brightness":255,"timeout":1}'
```

**MQTT API:**
```bash
mosquitto_pub -h localhost -t "openevse/led/set" \
  -m '{"state":"ready","color":"#0000FF","brightness":255,"timeout":1}'
```

**Result**: API returns 200 OK with `{"msg":"done"}`, but LED color/brightness does not change when device enters ready state.

### Test 3: Setting override for "waiting" state (WORKS)
**HTTP API:**
```bash
curl -X POST http://openevse2.local/led -H "Content-Type: application/json" \
  -d '{"state":"waiting","color":"#FFA500","brightness":128,"timeout":2}'
```

**MQTT API:**
```bash
mosquitto_pub -h localhost -t "openevse/led/set" \
  -m '{"state":"waiting","color":"#FFA500","brightness":128,"timeout":2}'
```

**Result**: ✓ Works correctly - LED changes to orange at 50% brightness when in waiting state.

### Test 4: Setting override for "all" states (WORKS)
**HTTP API:**
```bash
curl -X POST http://openevse2.local/led -H "Content-Type: application/json" \
  -d '{"state":"all","color":"#800080","brightness":255,"timeout":2}'
```

**MQTT API:**
```bash
mosquitto_pub -h localhost -t "openevse/led/set" \
  -m '{"state":"all","color":"#800080","brightness":255,"timeout":2}'
```

**Result**: ✓ Works correctly - LED changes to purple in all states, including ready and charging.

## Expected Behavior
When setting LED override for `ready` or `charging` states, the LED should:
1. Accept the override configuration (API returns 200 OK)
2. Apply the specified color and brightness when the device enters that state
3. Revert after the timeout expires

## Actual Behavior
- API accepts the override (returns 200 OK)
- LED color and brightness remain at default values when device enters `ready` or `charging` state
- Override appears to be stored but not applied

## Working States
- ✓ `waiting` - Override applies correctly
- ✓ `all` - Override applies correctly (even in ready/charging states)
- ✓ `off` - (not tested, but likely works based on similar implementation)
- ✓ `error` - (not tested, but likely works based on similar implementation)

## Broken States
- ✗ `ready` - Override accepted but not applied
- ✗ `charging` - Override accepted but not applied

## Workaround
Use `state:"all"` instead of specific state names. This applies the override across all states including ready and charging.

## Possible Causes
1. State name mismatch between API input validation and LED control logic
2. LED control code may use different state identifiers than the API expects
3. Override lookup logic may not properly match `ready` and `charging` states
4. State transitions may skip override application for certain states

## Suggested Investigation
1. Check LED state enumeration in `src/lcd_common.h` or similar LED control files
2. Verify state name mapping in the LED override handler (`handleLed` in `src/web_server.cpp`)
3. Review LED update logic to ensure it checks overrides for all state types
4. Check if `ready` and `charging` states have different internal representations

## Testing Notes
- Both HTTP API and MQTT API exhibit the same behavior
- No error messages or warnings in device logs
- API validation accepts all state values correctly
- The `all` state workaround confirms the LED hardware and override mechanism work correctly
