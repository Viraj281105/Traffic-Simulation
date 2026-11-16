# UrbanFlow signal-head reference firmware (MicroPython, ESP32 / Pi Pico W).
#
# WRITTEN, NOT RUN ON A BOARD. Syntax-checked only (py_compile in the test
# suite). Do not connect it to a real signal head or a road-side cabinet; it is
# a teaching/bench reference for LED lamps on a breadboard.
#
# Topics: subscribe urbanflow/hw/<DEVICE>/command, publish .../status.
# Same interlock rules as backend/src/hardware_bridge/interlock.py.

import json
import time

import machine
import network
from umqtt.simple import MQTTClient

# ---- configuration (edit before flashing) ---------------------------------
WIFI_SSID = "CHANGE_ME"
WIFI_PASSWORD = "CHANGE_ME"
MQTT_HOST = "192.168.1.10"  # your LAN broker, e.g. mosquitto
MQTT_PORT = 1883
DEVICE = "bench-head-1"

# GPIO pins per approach: (red, amber, green). Group 0 = N,S; group 1 = E,W.
PINS = {
    "N": (2, 3, 4),
    "E": (5, 6, 7),
    "S": (8, 9, 10),
    "W": (11, 12, 13),
}
MIN_AMBER_MS = 3000
MIN_ALL_RED_MS = 1000
HEARTBEAT_TIMEOUT_MS = 2000
FAILSAFE_HOLD_MS = 2000
FAILSAFE_MODE = "flashing_red"  # or "all_red"
FLASH_MS = 500
STATUS_MS = 1000
# ---------------------------------------------------------------------------

APPROACHES = ("N", "E", "S", "W")
GROUP = {"N": 0, "S": 0, "E": 1, "W": 1}
COLOURS = ("red", "amber", "green", "red_amber")
GO = ("green", "amber", "red_amber")

lamps = {h: [machine.Pin(p, machine.Pin.OUT, value=0) for p in PINS[h]] for h in APPROACHES}

heads = {h: "red" for h in APPROACHES}
desired = {h: "red" for h in APPROACHES}
since = {h: time.ticks_ms() for h in APPROACHES}
failsafe = False
fs_since = time.ticks_ms()
recover = False
last_rx = time.ticks_ms()
last_seq = -1
status_seq = 0
last_status = 0
topic_cmd = ("urbanflow/hw/%s/command" % DEVICE).encode()
topic_status = ("urbanflow/hw/%s/status" % DEVICE).encode()


def elapsed(t0):
    return time.ticks_diff(time.ticks_ms(), t0)


def drive():
    flash_on = (time.ticks_ms() // FLASH_MS) % 2 == 0
    for h in APPROACHES:
        c = heads[h]
        red = c in ("red", "red_amber") or (c == "flashing_red" and flash_on)
        amber = c in ("amber", "red_amber")
        green = c == "green"
        r, a, g = lamps[h]
        r.value(1 if red else 0)
        a.value(1 if amber else 0)
        g.value(1 if green else 0)


def conflicting():
    groups = set()
    for h in APPROACHES:
        if heads[h] in GO:
            groups.add(GROUP[h])
    return len(groups) > 1


def set_head(h, colour):
    heads[h] = colour
    since[h] = time.ticks_ms()


def trip(reason):
    global failsafe, fs_since, recover
    if not failsafe:
        failsafe = True
        colour = "flashing_red" if FAILSAFE_MODE == "flashing_red" else "red"
        for h in APPROACHES:
            set_head(h, colour)
        print("failsafe:", reason)
    fs_since = time.ticks_ms()
    recover = False


def step():
    global failsafe, recover
    if failsafe:
        if recover and elapsed(fs_since) >= FAILSAFE_HOLD_MS:
            failsafe = False
            for h in APPROACHES:
                set_head(h, "red")
        return
    for h in APPROACHES:
        c, d = heads[h], desired[h]
        if c == d:
            continue
        if d == "red":
            if c == "green":
                set_head(h, "amber")
            elif c == "red_amber":
                set_head(h, "red")
            elif c == "amber" and elapsed(since[h]) >= MIN_AMBER_MS:
                set_head(h, "red")
        elif c == "red":
            if d in ("green", "red_amber"):
                ok = True
                for x in APPROACHES:
                    if GROUP[x] != GROUP[h]:
                        if heads[x] != "red" or elapsed(since[x]) < MIN_ALL_RED_MS:
                            ok = False
                if ok:
                    set_head(h, d)
        elif d != "red_amber":
            set_head(h, d)
    if conflicting():
        trip("conflict_detected")


def valid(body):
    if not isinstance(body, dict) or body.get("v") != 1:
        return False
    if body.get("device") != DEVICE or body.get("type") not in ("cmd", "hb"):
        return False
    seq = body.get("seq")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
        return False
    if body["type"] == "cmd":
        hs = body.get("heads")
        if not isinstance(hs, dict) or len(hs) != 4:
            return False
        for h in APPROACHES:
            if hs.get(h) not in COLOURS:
                return False
        groups = set()
        for h in APPROACHES:
            if hs[h] in GO:
                groups.add(GROUP[h])
        if len(groups) > 1:
            return False
    return True


def on_message(topic, payload):
    global last_seq, last_rx, recover, desired
    try:
        body = json.loads(payload)
    except ValueError:
        body = None
    if len(payload) > 2048 or not valid(body):
        trip("invalid_command")
        return
    seq = body["seq"]
    if seq <= last_seq:
        return  # duplicate or reordered: ignore, do not refresh the watchdog
    last_seq = seq
    last_rx = time.ticks_ms()
    recover = True
    if body["type"] == "cmd":
        desired = body["heads"]
        publish_status(seq, body.get("ts"))


def publish_status(ack_seq=None, ack_ts=None):
    global status_seq, last_status
    status_seq += 1
    last_status = time.ticks_ms()
    msg = {
        "v": 1,
        "device": DEVICE,
        "seq": status_seq,
        "ts": time.ticks_ms() / 1000.0,
        "mode": "failsafe" if failsafe else "normal",
        "heads": heads,
        "lastSeq": last_seq,
        "ackSeq": ack_seq,
        "ackTs": ack_ts,
    }
    client.publish(topic_status, json.dumps(msg))


def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    t0 = time.ticks_ms()
    while not wlan.isconnected():
        if elapsed(t0) > 20000:
            raise RuntimeError("wifi timeout")
        time.sleep_ms(200)


def main():
    global client
    # Safe power-on state: flashing red until the first valid message arrives.
    trip("power_on")
    wifi_connect()
    client = MQTTClient("urbanflow-" + DEVICE, MQTT_HOST, MQTT_PORT, keepalive=10)
    client.set_callback(on_message)
    client.connect()
    client.subscribe(topic_cmd)
    while True:
        try:
            client.check_msg()
        except OSError:
            trip("link_lost")
            time.sleep_ms(500)
            try:
                client.connect()
                client.subscribe(topic_cmd)
            except OSError:
                pass
        if not failsafe and elapsed(last_rx) > HEARTBEAT_TIMEOUT_MS:
            trip("heartbeat_timeout")
        step()
        drive()
        if elapsed(last_status) >= STATUS_MS:
            try:
                publish_status()
            except OSError:
                pass
        time.sleep_ms(20)


client = None
main()
