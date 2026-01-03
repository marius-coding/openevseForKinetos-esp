# Feature Request: Temporary LED Color Override

## Overview
Add MQTT and HTTP API commands to temporarily override LED strip colors for visual notifications or custom status indicators, independent of the normal EVSE state-based LED behavior.

## MQTT API

### Set Color Override
**Topic:** `<base-topic>/led/set`

**Payload Format:**
```json
{
  "state": "waiting",
  "color": "#ABCDEF",
  "brightness": 255,
  "timeout": 5
}
```

**Parameters:**
- `state` (string, required): LED state to override. Valid values:
  - `"off"` - LED off state
  - `"error"` - Error/Fault states (includes vent required, GFI fault, etc.)
  - `"ready"` - Ready state (not connected, waiting for vehicle)
  - `"waiting"` - Waiting state (vehicle connected, ready to charge)
  - `"charging"` - Charging state (actively charging)
  - `"custom"` - Custom state
  - `"default"` - Default/Fallback state
  - `"all"` - Override color regardless of LED state
- `color` (string, required): RGB color in hex format (`#RRGGBB`)
- `brightness` (number, optional): LED brightness level (0-255). If omitted, uses current configured brightness
- `timeout` (number, required): Duration in hours before automatic reset
  - `0` = No automatic reset (manual reset required)
  - `> 0` = Automatic reset after specified hours

**Example Messages:**
```bash
# Override LED to purple for 2 hours in all states
<base-topic>/led/set {"state":"all","color":"#800080","timeout":2}

# Override LED to orange only in waiting state, with 50% brightness, no timeout
<base-topic>/led/set {"state":"waiting","color":"#FFA500","brightness":128,"timeout":0}

# Override charging state to bright green for 1 hour
<base-topic>/led/set {"state":"charging","color":"#00FF00","brightness":255,"timeout":1}
```

### Reset Color Override
**Topic:** `<base-topic>/led/reset`

**Payload:** None (any payload ignored)

Immediately clears any active LED color override and restores default state-based LED behavior.

## HTTP API

### POST /led
Set temporary LED color override.

**Request Body:**
```json
{
  "state": "waiting",
  "color": "#ABCDEF",
  "brightness": 200,
  "timeout": 5
}
```

**Parameters:** Same as MQTT API above

**Valid State Values:**
- `off`, `error`, `ready`, `waiting`, `charging`, `custom`, `default`, `all`

**Response:**
```json
{
  "msg": "done"
}
```

**Error Response:**
```json
{
  "msg": "Invalid state value"
}
```

### DELETE /led
Clear LED color override and restore default behavior.

**Response:**
```json
{
  "msg": "done"
}
```

## Implementation Notes
- LED override brightness parameter is optional; if not provided, uses the configured `led_brightness` value
- When brightness is specified in override, it temporarily overrides the global `led_brightness` setting
- Override state should persist across LED state changes until timeout expires or manual reset
- When timeout expires, LED should go back to normal state-based color and configured brightness
- Override settings should NOT persist across device reboots
- Feature only applies when `RGB_LED` is enabled at build time (NEO_PIXEL_PIN or discrete RGB LEDs)
- Priority: LED override should have higher priority than normal LED state colors but lower than WiFi status indicators (AP mode, connecting states)
- Multiple state-specific overrides can be active simultaneously (e.g., override "charging" and "ready" separately)

## Implementation Status

✅ **Completed** - Feature fully implemented in the following files:

### Core LED Management (`src/LedManagerTask.h`, `src/LedManagerTask.cpp`)
- Added `ColorOverride` structure to track override state per LED state (8 states supported)
- Implemented `setColorOverride()` method to set color, brightness, and timeout
- Implemented `clearColorOverride()` method to clear one or all overrides
- Implemented `checkOverrideTimeouts()` to automatically expire timed overrides
- Integrated override checking into color application logic for WS2812FX and discrete RGB LEDs
- Added `getNextTimeoutCheck()` to schedule task wake-ups for timeout handling

### MQTT API (`src/mqtt.cpp`)
- Added handler for `<base-topic>/led/set` topic
- Added handler for `<base-topic>/led/reset` topic
- Subscribed to LED control topics in `subscribeTopics()`
- Parses JSON payload and validates color format (#RRGGBB)

### HTTP API (`src/web_server.cpp`)
- Implemented `handleLed()` function for POST and DELETE requests
- Registered `/led` endpoint in server initialization
- POST endpoint validates state, color format, and timeout parameters
- DELETE endpoint clears all active overrides

### Testing (`test/led.http`)
- Created comprehensive test suite for REST API
- Includes valid and invalid request tests
- Tests multiple state overrides, timeout scenarios, and error handling

## Use Cases
- Visual notification for external systems (e.g., home automation alerts)
- Temporary visual identification of specific charging stations in multi-unit installations
- Integration with time-of-use rate indicators (e.g., green during cheap rate periods)
- Custom status display for solar charging modes or grid export scenarios

## Technical Details

### Affected Components
- `src/LedManagerTask.cpp` / `src/LedManagerTask.h` - LED control logic
- `src/mqtt.cpp` - MQTT message handling
- `src/web_server.cpp` - HTTP endpoint implementation
- `src/app_config.h` / `src/app_config.cpp` - Configuration (if persistence needed)

### State Management
The LED override should be managed as a runtime state in `LedManagerTask` with the following properties:
- Override active flag per LED state (off, error, ready, waiting, charging, custom, default, all)
- Target state filter (maps to LED color states: `led_color_off`, `led_color_red`, `led_color_green`, `led_color_yellow`, `led_color_teal`, `led_color_violet`, `led_color_white`)
- Note: `led_color_blue` is unused in normal EVSE operation
- Override color (24-bit RGB value) per state
- Override brightness (0-255) per state
- Timeout expiration timestamp per state
- Original color and brightness backup (for restoration)
