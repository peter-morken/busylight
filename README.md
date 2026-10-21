# Busylight

A standalone desk busylight: a Wemos D1 Mini (ESP8266), a red/yellow/green LED traffic light module and a TTP223 capacitive touch button. It runs [ESPHome](https://esphome.io) firmware with all wireless turned off. There's no Wi-Fi, Home Assistant API, OTA or captive portal; it works purely from the touch button.

## Behaviour

Tapping the button runs a focus timer:

| Current light | Tap → |
|---|---|
| Green, amber or off | **Red** for 25 min, then **amber** for 5 min, then **green** |
| Red | **Green** immediately (timer cancelled) |

The last colour is restored after a power cut. The durations are set by `busy_minutes` and `break_minutes` under `substitutions:` in `busylight.yaml`.

## Parts

- Wemos D1 Mini (ESP8266)
- LED traffic light module (R / Y / G / GND, with onboard resistors)
- TTP223 capacitive touch module
- USB cable and a 5 V USB power supply

## Wiring

```
                 Wemos D1 Mini
              ┌──────────────────┐
  USB 5V ────►│ USB              │
              │ D5 (GPIO14) ─────┼──► R   ┐
              │ D6 (GPIO12) ─────┼──► Y   ├ Traffic light
              │ D7 (GPIO13) ─────┼──► G   │
              │ G  ──────────────┼──► GND ┘
              │ 3V3 ─────────────┼──► VCC ┐
              │ D8 (GPIO15) ◄────┼─── I/O ├ TTP223 touch
              │ G  ──────────────┼──► GND ┘
              └──────────────────┘
```

| Module pin | D1 Mini pin |
|---|---|
| Traffic light R | D5 |
| Traffic light Y | D6 |
| Traffic light G | D7 |
| Traffic light GND | G |
| TTP223 VCC | 3V3 (not 5V) |
| TTP223 I/O | D8 |
| TTP223 GND | G |

Notes:

- The D1 Mini has a single G pin, so join the ground wires (with a Wago connector, a breadboard rail or a splice) and run one wire to G.
- Leave the TTP223's A and B solder pads open, which is how it ships. That gives a momentary output that goes HIGH when touched.
- D8 is a boot strapping pin and must be LOW at power-up. The TTP223 idles LOW and the D1 Mini has a 10k pull-down on D8, so this is fine as long as **the pad isn't touched while the board powers up**. The TTP223 also calibrates itself at power-up.
- A second traffic light module can be wired in parallel on the same pins.

## Building and flashing

Without OTA, every update goes over USB.

**Browser (no install):** compile the firmware with ESPHome, then open [web.esphome.io](https://web.esphome.io) in Chrome or Edge. Click **Connect**, then **Install**, and select `firmware.factory.bin`.

**ESPHome CLI** (via Docker on Linux; replace `/dev/ttyUSB0` with the board's port):

```bash
docker run --rm -v "$PWD":/config --device /dev/ttyUSB0 ghcr.io/esphome/esphome run busylight.yaml --device /dev/ttyUSB0
```

On Linux, check `/dev/serial/by-id/` first to make sure the port is really the D1 Mini and not another USB serial device.
