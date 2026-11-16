# Signal-head reference firmware (MicroPython)

**Status: WRITTEN, NOT RUN ON A BOARD.** `main.py` has only been syntax-checked
(`py_compile` in `backend/tests/hardware_bridge`). It has never executed on an
ESP32 or Pico W, and it has not been tested against a broker. It is a bench
reference for LEDs on a breadboard. Do not connect it to a real signal head,
mains-powered lamp driver or any roadside equipment.

It mirrors the on-device interlock in `backend/src/hardware_bridge/interlock.py`:
never two conflicting "go" heads (N,S vs E,W); green to red always via amber
for at least `MIN_AMBER_MS`; a head leaves red only after all conflicting heads
have been red for `MIN_ALL_RED_MS`; flashing red (or all red) at power-on, on
heartbeat timeout, on an invalid or conflicting command and on link loss,
released only after a valid message and `FAILSAFE_HOLD_MS`.

## Topics

- subscribes `urbanflow/hw/<DEVICE>/command`: JSON
  `{"v":1,"type":"cmd","device":"...","seq":N,"ts":T,"heads":{"N":"green","E":"red","S":"green","W":"red"}}`
  (colours `red`, `amber`, `green`, `red_amber`) or `{"v":1,"type":"hb","device","seq","ts"}`
- publishes `urbanflow/hw/<DEVICE>/status` (mode, heads, lastSeq, ackSeq/ackTs)

## Wiring (per approach: 3 LEDs, active-high)

Each GPIO drives one LED through a 330 ohm resistor to GND (3.3 V logic, about
5 mA per LED). Default pins in `PINS` (red, amber, green):

| Approach | Red | Amber | Green |
|----------|-----|-------|-------|
| N | GP2 | GP3 | GP4 |
| E | GP5 | GP6 | GP7 |
| S | GP8 | GP9 | GP10 |
| W | GP11 | GP12 | GP13 |

These numbers suit a Pi Pico W. On an ESP32 several of them are reserved or
unavailable (flash, boot-strap pins); edit `PINS` to free GPIOs of your board
(for example 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33).

## Flashing steps (MicroPython, ESP32 or Pico W)

1. Install MicroPython for your board from micropython.org (ESP32:
   `esptool.py --chip esp32 erase_flash`, then
   `esptool.py --chip esp32 --baud 460800 write_flash -z 0x1000 <firmware>.bin`;
   Pico W: hold BOOTSEL, plug in USB, copy the `.uf2` to the drive that appears).
2. `pip install mpremote`.
3. Edit the configuration block at the top of `main.py`: `WIFI_SSID`,
   `WIFI_PASSWORD`, `MQTT_HOST` (a broker on your LAN, for example mosquitto),
   `DEVICE` (must match `[A-Za-z0-9_-]{1,32}`), `PINS`.
4. Install the MQTT client once: `mpremote mip install umqtt.simple`
   (the board needs Wi-Fi first; see `mpremote` docs).
5. Copy and run: `mpremote cp main.py :main.py` then `mpremote reset`
   (MicroPython runs `main.py` at boot). To test without installing:
   `mpremote run main.py`.
6. Publish commands with the bridge (`MqttHwBus` in
   `backend/src/hardware_bridge/bus.py`; requires `pip install paho-mqtt`) or
   by hand: `mosquitto_pub -t urbanflow/hw/bench-head-1/command -m '{...}'`.
   The head stays in flashing red until it receives a valid command or heartbeat.

## Known gaps

No authentication or TLS on the broker link, no persistent config, no
real-time guarantees (the loop polls every 20 ms), and no conflict monitor
independent of the CPU. This is not a certified controller.
