# Reading broadcast-type BLE toys with a Mac — Love Spouse as the example

[中文](README.md) | **English**

> **Use your iPhone directly as the broadcaster**: no Android phone, no extra hardware. A Mac does the "listening" — record what the phone sends to the toy, figure out the pattern — then send it yourself from an iPhone (or the Mac).
> For anyone who wants their AI companion to control a toy remotely and only has an iPhone: the usual approach online is to send **manufacturer data** with a tool like nRF Connect, but iOS doesn't let apps set custom manufacturer data, so it simply can't be sent from an iPhone.
>
> **The method works for any "broadcast-type" toy** (the phone shouts, the toy listens). The concrete data here is for Love Spouse; for another brand you'll need to record your own — section 2.5 shows how to find it.

---

## TL;DR

| | |
|---|---|
| How the toy receives commands | **No connection.** The phone keeps broadcasting the command in BLE **advertisements**; the toy just listens |
| Where the command lives | The iPhone app encodes it into a list of **13 16-bit service UUIDs** (iOS doesn't allow custom manufacturer data, so this is the only place it fits) |
| Encryption / rolling codes | **None.** The same level sends exactly the same thing every time — record it and replay it |
| Pattern | Each channel has a "stop" command; levels 1–9 = stop XOR a fixed value per level, same table for every channel (section 3) |
| What you need | A Mac, a phone with the official app, the toy |

The example data applies to toys controlled by the **Love Spouse** app (several Chinese brands, e.g. 合欢兔 / MuSe, use the same protocol). Models and app versions may differ — recording your own per section 2 is the safest.

---

## 0. Prerequisites

- macOS with Bluetooth
- Python 3.11 from Homebrew: `brew install python@3.11`
- Love Spouse installed on your phone and able to control the toy

---

## 1. Why "connecting" works but the toy won't move

Most toy tutorials use a **GATT connection**: connect to the toy → find a characteristic → write bytes to it.

These toys can be connected to as well (they expose services like `FF60`, `AE00`), but they ignore anything you write — they don't take commands over the connection at all. The official app uses **peripheral-mode advertising**: the phone pretends to be a BLE device and puts the command in its advertisement packets, and the toy listens nearby.

The Android app puts the command in **Manufacturer Specific Data**, and that layer has already been reverse-engineered publicly (see Acknowledgements). But iOS only lets apps put a **local name and service UUIDs** in advertisements, so the iPhone app packs it differently, and the Android approach can't be reproduced on an iPhone. This guide covers the iPhone layer.

So step one isn't connecting to the toy — it's **listening to what the phone is shouting**.

### Which kind is your toy?

- Bluetooth on, app open but **not connected** to the toy, and tapping a level still moves it → most likely **broadcast-type**; this guide applies
- The app makes you "scan → connect" to a device before you can control it → most likely **connection-type**; look for a GATT-characteristic tutorial instead

---

## 2. Recording advertisements (the Mac listens)

### 2.1 Set up

```bash
/opt/homebrew/bin/python3.11 -m venv blevenv
blevenv/bin/pip install -U pip bleak
```

> ⚠️ **Don't use the Python that ships with Xcode.** Its `Python.app` has no Bluetooth usage description, so macOS kills it the moment it touches Bluetooth — without any error.

### 2.2 Patch one line in bleak (important)

By default macOS **coalesces duplicate advertisements**: when a device's advertisement changes, it may only be reported once, so you'll miss half the level changes.

Open `blevenv/lib/python3.11/site-packages/bleak/backends/corebluetooth/CentralManagerDelegate.py` and find:

```python
scanForPeripheralsWithServices_options_(_service_uuids, None)
```

Replace `None` with:

```python
{"kCBScanOptionAllowDuplicates": True}
```

### 2.3 Recording script [`blelog.py`](blelog.py)

Logs only advertisements whose service UUIDs start with a given value (default `08f9`, the fixed Love Spouse header), one line each time the content changes:

```python
"""Usage: blelog.py <seconds> <output file> [UUID prefix, default 08f9]"""
import asyncio, sys, time, json, datetime
from bleak import BleakScanner

seconds = float(sys.argv[1]); out = open(sys.argv[2], "a")
PREFIX = sys.argv[3] if len(sys.argv) > 3 else "08f9"
last = {}

def cb(dev, adv):
    svc = [s[4:8] for s in (adv.service_uuids or [])]   # the 16-bit short UUIDs
    if not svc or svc[0] != PREFIX:
        return
    key = " ".join(svc)
    if last.get(dev.address) == key:
        return
    last[dev.address] = key
    t = time.time()
    line = json.dumps({"hms": datetime.datetime.fromtimestamp(t).strftime("%H:%M:%S"), "svc": svc})
    print(line, flush=True); out.write(line + "\n"); out.flush()

async def main():
    async with BleakScanner(cb):
        await asyncio.sleep(seconds)

asyncio.run(main())
```

### 2.4 Record

> ⚠️ **Run it from Terminal.app.** Running it directly inside an IDE or another tool won't get Bluetooth permission. The first run will prompt for Bluetooth access — allow it.

```bash
blevenv/bin/python blelog.py 600 cmds.jsonl
```

During those 10 minutes, tap through the app **in a fixed order**, about 5 seconds per level:

1. Mode 1: levels 1 → 9
2. Mode 2: levels 1 → 9
3. Stop

Then match each line to the level you tapped, by time.

### 2.5 A different toy: find it first

The script above only looks for the Love Spouse `08f9` header. For another brand, start with the "record everything" version, [`blescan.py`](blescan.py), which logs every nearby advertisement including manufacturer data:

```python
"""Usage: blescan.py <seconds> <output file> — log every nearby advertisement, one line per change"""
import asyncio, sys, time, json
from bleak import BleakScanner

seconds = float(sys.argv[1]); out = open(sys.argv[2], "a")
seen = set()

def cb(dev, adv):
    rec = {
        "t": round(time.time(), 2),
        "name": adv.local_name or dev.name,
        "mfr": {str(k): v.hex() for k, v in (adv.manufacturer_data or {}).items()},  # manufacturer data
        "svc": list(adv.service_uuids or []),                                        # service UUIDs
        "sdata": {k: v.hex() for k, v in (adv.service_data or {}).items()},          # service data
    }
    key = json.dumps({k: rec[k] for k in ("name", "mfr", "svc", "sdata")}, sort_keys=True)
    if key not in seen:
        seen.add(key)
        line = json.dumps(rec, ensure_ascii=False)
        print(line, flush=True); out.write(line + "\n"); out.flush()

async def main():
    async with BleakScanner(cb):
        await asyncio.sleep(seconds)

asyncio.run(main())
```

How to find it: first record 30 seconds **without touching anything** to see what's normally around; then start changing levels in the app. The entry that **newly appears and changes along with your taps** is the one. Check which field changes:

- **Sent from an iPhone**: iOS doesn't allow custom manufacturer data, so the command can only be in `svc` (service UUIDs) or the name — that's what Love Spouse does
- **Sent from Android**: usually in `mfr` (manufacturer data)

Once found, pass its fixed prefix as the third argument to `blelog.py` (e.g. `blelog.py 600 cmds.jsonl 1a2b`) and record again following 2.4. If the changes are in manufacturer data, just read them from the `blescan.py` output.

---

## 3. Reading the advertisement (Love Spouse example)

### 3.1 The 13 UUIDs

```
08f9 2349 cbae d1c1 | XXXX 0bYY | 0d0c 0f0e 1110 1312 1514 1716 1918
└──── fixed head ──┘   └command┘   └───────────── fixed tail ────────────┘
```

Only the 5th and 6th change (and the `0b` half of the 6th doesn't), so **a command is really just 3 bytes**.

### 3.2 "Stop" for each channel

| Channel | Stop (5th & 6th UUID) |
|---|---|
| Motion (main body) | `1f5e 0b0c` |
| Vibe (main body) | `982e 0b7f` |
| Suction (separate attachment) | `9c6e 0b3d` |

Motion and Vibe can run at the same time.

### 3.3 The level pattern

Convert the iPhone advertisement back to the Android 3-byte command `(a, b, c)`:

```
5th UUID = (b ^ 0x0A)(a ^ 0xBB)
6th UUID = 0b (c ^ 0x71)
```

At the `(a, b, c)` level, **each level = the stop command's a, b, c each XORed with a fixed value**, and all channels share the same table:

| Level | XOR (a, b, c) |
|---|---|
| 1 | `01 89 11` |
| 2 | `02 12 23` |
| 3 | `03 9B 32` |
| 4 | `04 24 46` |
| 5 | `05 AD 57` |
| 6 | `06 36 65` |
| 7 | `07 BF 74` |
| 8 | `08 48 8C` |
| 9 | `09 C1 9D` |

(The XOR on `a` is just the level number.)

Why it's so regular: the Android command is "fixed prefix + mode byte", run through CRC16 and then two rounds of whitening (XOR with a fixed byte stream). Both CRC and XOR are linear — a fixed difference in the input gives a fixed difference in the output — so changing only the mode byte always changes the result by the same XOR. Cross-check: "Motion · Stop" converted back to Android is `E5 15 7D`, exactly the last three bytes of mode 0x00 in the public Android table.

So once you have a channel's "stop", levels 1–9 can be computed. Full table:

| Level | Motion | Vibe | Suction |
|---|---|---|---|
| Stop | `1f5e 0b0c` | `982e 0b7f` | `9c6e 0b3d` |
| 1 | `965f 0b1d` | `112f 0b6e` | `156f 0b2c` |
| 2 | `0d5c 0b2f` | `8a2c 0b5c` | `8e6c 0b1e` |
| 3 | `845d 0b3e` | `032d 0b4d` | `076d 0b0f` |
| 4 | `3b5a 0b4a` | `bc2a 0b39` | `b86a 0b7b` |
| 5 | `b25b 0b5b` | `352b 0b28` | `316b 0b6a` |
| 6 | `2958 0b69` | `ae28 0b1a` | `aa68 0b58` |
| 7 | `a059 0b78` | `2729 0b0b` | `2369 0b49` |
| 8 | `5756 0b80` | `d026 0bf3` | `d466 0bb1` |
| 9 | `de57 0b91` | `5927 0be2` | `5d67 0ba0` |

Suction levels 1–9 were computed from the pattern and checked against what the phone actually sends — byte for byte identical.

---

## 4. Replay to verify (the Mac speaks)

Let the Mac act as the "phone" and broadcast a command; if the toy moves, you read it right.

```bash
blevenv/bin/pip install pyobjc-framework-CoreBluetooth
```

The core is just:

```python
from CoreBluetooth import CBPeripheralManager, CBUUID, CBAdvertisementDataServiceUUIDsKey

HEAD = ["08f9", "2349", "cbae", "d1c1"]
TAIL = ["0d0c", "0f0e", "1110", "1312", "1514", "1716", "1918"]

def advertise(pm, code):              # code e.g. "b25b 0b5b" (Motion · level 5)
    uuids = [CBUUID.UUIDWithString_(u) for u in HEAD + code.split() + TAIL]
    pm.startAdvertising_({CBAdvertisementDataServiceUUIDsKey: uuids})
```

The full script (Bluetooth state callback, pick a command by number, full table built in) is [`replay.py`](replay.py) — also run it from **Terminal**. (Its comments and labels are in Chinese: 动 = Motion, 震 = Vibe, 吸 = Suction, 停止 = Stop, 档 = level.)

> 💡 **Stopping the broadcast ≠ stopping the toy.** The toy stays at the last level it heard; to stop it, send that channel's "stop" command.
>
> 💡 In testing, Motion and Vibe respond to replay from the Mac, but the Suction attachment ignores the Mac and works fine from an iPhone. Possibly macOS advertises less often, or the UUIDs get moved into the scan response and that attachment is pickier.

---

## 5. Hand it to your AI

Once a computer can send commands, letting your AI control it is just "turn a button into a tool it can call":

- **Simplest**: if your AI can run commands (e.g. Claude Code), let it call the replay script
- **Away from the computer**: use the iPhone as the broadcaster. In your own app, broadcast the same 13 UUIDs with `CBPeripheralManager`, then expose an endpoint: AI calls endpoint → phone broadcasts → toy moves

Sending a command from an iPhone takes only this (Swift):

```swift
import CoreBluetooth

let head = ["08F9", "2349", "CBAE", "D1C1"]
let tail = ["0D0C", "0F0E", "1110", "1312", "1514", "1716", "1918"]

// pm is a CBPeripheralManager in the .poweredOn state; code e.g. "B25B 0B5B" (Motion · level 5)
func advertise(_ pm: CBPeripheralManager, _ code: String) {
    let ids = (head + code.split(separator: " ").map(String.init) + tail).map { CBUUID(string: $0) }
    pm.stopAdvertising()
    pm.startAdvertising([CBAdvertisementDataServiceUUIDsKey: ids])
}
```

In testing, all three channels can be controlled from an iPhone — including Suction, which ignores the Mac.

> ⚠️ When an iOS app goes to the background, its advertised service UUIDs are moved into the "overflow area", and some toys won't hear them. For background use, add `bluetooth-peripheral` to the background modes in Info.plist, and test foreground / background yourself.

---

## 6. Safety note

**Anyone can hear the broadcast.** While you're using it, anyone nearby with a scanner app can see, record and replay it. That's how these toys are designed, not something this guide introduces. For learning and research only.

---

## Common pitfalls

| Symptom | Cause |
|---|---|
| Script quits instantly with no error | Using Xcode's bundled Python — use Homebrew's |
| Nothing gets recorded | Not run from Terminal, or Bluetooth permission not granted |
| Only some level changes are recorded | bleak not patched for `AllowDuplicates` (2.2) |
| Connected to the toy, wrote a command, nothing happens | It doesn't take commands over a connection — see section 1 |
| Stopped broadcasting but the toy keeps going | Send the "stop" command, don't just stop broadcasting |

---

## Acknowledgements

- [Cami-Ose/muse-toy-broadcaster](https://github.com/Cami-Ose/muse-toy-broadcaster) (MIT): reverse-engineered implementation of the MuSe / Love Spouse **Android** advertising protocol — manufacturer data format, CRC16 + double whitening, and the command table. What this guide adds is the **iPhone** format that encodes the command in service UUIDs, and the conversion between it and the Android command
- [bleak](https://github.com/hbldh/bleak): cross-platform Python BLE library
- [PyObjC](https://github.com/ronaldoussoren/pyobjc): lets Python call macOS CoreBluetooth

## License

[MIT](LICENSE) © 2026 Tilia & Quercus
