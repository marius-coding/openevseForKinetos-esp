#ifndef LED_MANAGER_TASK_H
#define LED_MANAGER_TASK_H

#include <Arduino.h>
#include <MicroTasks.h>

#include "evse_man.h"

#if defined(NEO_PIXEL_PIN) && defined(NEO_PIXEL_LENGTH)
#define RGB_LED 1
#elif defined(RED_LED) && defined(GREEN_LED) && defined(BLUE_LED)
#define RGB_LED 1
#else
#define RGB_LED 0
#endif

enum LedState
{
  LedState_Test_Red,
  LedState_Test_Green,
  LedState_Test_Blue,
  LedState_Off,
  LedState_Evse_State,
  LedState_WiFi_Access_Point_Waiting,
  LedState_WiFi_Access_Point_Connected,
  LedState_WiFi_Client_Connecting,
  LedState_WiFi_Client_Connected
};

class LedManagerTask : public MicroTasks::Task
{
  private:
    EvseManager *_evse;

    LedState state;

    bool wifiClient;
    bool wifiConnected;

    bool flashState;

    uint8_t brightness;

    MicroTasks::EventListener onStateChange;

    // LED color override state management
    struct ColorOverride {
      bool active;
      uint32_t color;
      uint8_t brightness;  // 0 = use global brightness, 1-255 = override brightness
      unsigned long timeout_ms;  // 0 = no timeout
      unsigned long set_time_ms;  // millis() when override was set
      
      ColorOverride() : active(false), color(0), brightness(0), timeout_ms(0), set_time_ms(0) {}
      
      bool isExpired() const {
        if (!active || timeout_ms == 0) return false;
        return (millis() - set_time_ms) >= timeout_ms;
      }
    };
    
    // Override state for each LED state
    ColorOverride _overrides[8];  // One for each: off, error, ready, waiting, charging, custom, default, all
    
    // Helper to get override index from state string
    int getOverrideIndex(const char* stateStr) const;
    
    // Check if any override has expired and clear it
    void checkOverrideTimeouts();
    
    // Calculate next timeout check interval (returns 0 for no active timeouts)
    unsigned long getNextTimeoutCheck() const;
    
#if RGB_LED
    // Apply color override if active for the given LCD color state
    uint32_t applyColorOverride(uint8_t lcdCol) const;
    
    // Get effective brightness considering overrides
    uint8_t getEffectiveBrightness(uint8_t lcdCol) const;
#endif

#if RGB_LED
#if defined(NEO_PIXEL_PIN) && defined(NEO_PIXEL_LENGTH) && defined(ENABLE_WS2812FX)
    void setAllRGB(uint32_t color, u_int8_t mode, u_int16_t speed);
    void setEvseAndWifiRGB(uint32_t evseColor, u_int8_t mode, u_int16_t speed);
#else
    void setAllRGB(uint8_t red, uint8_t green, uint8_t blue);
    void setEvseAndWifiRGB(uint8_t evseRed, uint8_t evseGreen, uint8_t evseBlue, uint8_t wifiRed, uint8_t wifiGreen, uint8_t wifiBlue);
#endif
#endif

#ifdef WIFI_LED
    void setWiFiLed(uint8_t state);
#endif

    LedState ledStateFromEvseState(uint8_t);
    void setNewState(bool wake = true);
    int getPriority(LedState state);

  protected:
    void setup();
    unsigned long loop(MicroTasks::WakeReason reason);

  public:
    LedManagerTask();

    void begin(EvseManager &evse);

    void setWifiMode(bool client, bool connected);

    void test();
    void testColor(uint32_t color);
    void clear();

    int getButtonPressed();

    void setBrightness(uint8_t brightness);
    void updateColors();
    
    // LED color override API
    bool setColorOverride(const char* stateStr, uint32_t color, uint8_t brightness, unsigned long timeout_hours);
    void clearColorOverride(const char* stateStr = nullptr);  // nullptr clears all
};

extern LedManagerTask ledManager;

#endif //  LED_MANAGER_TASK_H