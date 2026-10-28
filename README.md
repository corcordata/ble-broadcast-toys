# 用一台 Mac 读懂广播型蓝牙玩具：以 Love Spouse 为例

**中文** | [English](README.en.md)

> **直接拿你的 iPhone 当广播端**：不用安卓机，不买任何额外设备。一台 Mac 负责「听」，录下手机发给玩具的指令、看懂它的规律，再用 iPhone（或 Mac）自己发出去。
> 适合想让你的 AI 伴侣远程控制玩具、手边只有 iPhone 的人：网上现成的做法是用 nRF Connect 之类的工具发**厂商数据**，可 iOS 不允许 App 自定义厂商数据，在 iPhone 上根本发不出去。
>
> **方法适用于所有「广播型」玩具**（手机喊、玩具听）；文中的具体数据以 Love Spouse 为例，换一个牌子要自己录一遍，第 2.5 节讲怎么找。

---

## 先说结论

| | |
|---|---|
| 这类玩具怎么收指令 | **不走连接**。手机把指令塞进蓝牙**广播**里一直喊，玩具自己听 |
| 指令藏在哪 | iPhone 版 App 把指令编进一串 **13 个 16 位服务 UUID** 里（iOS 不允许 App 自定义厂商数据，只能这么塞） |
| 有没有加密 / 滚动码 | **没有**。同一档位每次发的完全一样，录下来原样重放就行 |
| 规律 | 每一路有一条「停止」指令，1～9 档 = 停止那条按档位 XOR 一个固定值，三路通用（见第 3 节） |
| 需要什么 | 一台 Mac、装了官方 App 的手机、玩具本身 |

示例数据适用于用 **Love Spouse** App 控制的玩具（国内常见的合欢兔、暮瑟等牌子用的是同一套）。不同型号、不同 App 版本可能有差别，照第 2 节自己录一遍最稳。

---

## 0. 准备

- macOS，带蓝牙
- Homebrew 装的 Python 3.11：`brew install python@3.11`
- 手机上装好 Love Spouse，玩具能被它正常控制

---

## 1. 为什么「连接」连得上却不动

网上大多数玩具教程走的是 **GATT 连接**：手机连上玩具 → 找到某个特征值 → 往里写字节。

这类玩具也能被连上（会露出 `FF60`、`AE00` 这类服务），但你往里写什么它都不理——因为它压根不从连接里收指令。官方 App 用的是**外设模式广播**：手机自己假装成一个蓝牙设备，把指令放在广播包里，玩具在旁边听。

Android 版 App 把指令放在广播的**厂商数据**（Manufacturer Specific Data）里，这一层已经有人公开拆过（见文末致谢）。但 iOS 只允许 App 在广播里放**名字和服务 UUID**，所以 iPhone 版 App 换了一种装法，照着 Android 的做法在 iPhone 上发不出去。这份教程补的就是 iPhone 这一层。

所以第一步不是去连玩具，而是**听手机在喊什么**。

### 怎么判断你的玩具是哪一种

- 把手机蓝牙打开、App 打开但**不连**玩具，点档位玩具也会动 → 大概率是**广播型**，这份教程适用
- App 里要先「搜索 → 连接」某个设备，连上之后才能控制 → 多半是**连接型**，要找 GATT 特征值那一类教程

---

## 2. 录广播（Mac 听）

### 2.1 建环境

```bash
/opt/homebrew/bin/python3.11 -m venv blevenv
blevenv/bin/pip install -U pip bleak
```

> ⚠️ **别用 Xcode 自带的 Python**。它的 `Python.app` 没写蓝牙用途说明，一碰蓝牙就被系统直接杀掉，连报错都没有。

### 2.2 改 bleak 的一行（重要）

macOS 默认会把**重复的广播合并**：同一个设备的广播内容变了，它可能只报一次。结果就是换档时只抓到一半。

打开 `blevenv/lib/python3.11/site-packages/bleak/backends/corebluetooth/CentralManagerDelegate.py`，找到：

```python
scanForPeripheralsWithServices_options_(_service_uuids, None)
```

把 `None` 换成：

```python
{"kCBScanOptionAllowDuplicates": True}
```

### 2.3 录制脚本 [`blelog.py`](blelog.py)

只记服务 UUID 以某一段开头的广播（默认 `08f9`，Love Spouse 的固定头），内容每变一次记一行：

```python
"""用法：blelog.py <秒数> <输出文件> [UUID 开头，默认 08f9]"""
import asyncio, sys, time, json, datetime
from bleak import BleakScanner

seconds = float(sys.argv[1]); out = open(sys.argv[2], "a")
PREFIX = sys.argv[3] if len(sys.argv) > 3 else "08f9"
last = {}

def cb(dev, adv):
    svc = [s[4:8] for s in (adv.service_uuids or [])]   # 取出 16 位短 UUID
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

### 2.4 开录

> ⚠️ **必须从「终端」App（Terminal.app）里跑**。在 IDE 或别的工具里直接跑，拿不到蓝牙权限。第一次运行系统会弹窗问蓝牙权限，点允许。

```bash
blevenv/bin/python blelog.py 600 cmds.jsonl
```

录的 10 分钟里，在手机 App 上**按固定顺序**点，每档停 5 秒左右：

1. 模式 1：1 → 9 档
2. 模式 2：1 → 9 档
3. 停止

最后按时间顺序把每一行和你点的档位一一对上。

### 2.5 换一个玩具：先把它找出来

上面的脚本默认只认 Love Spouse 的 `08f9` 开头。换一个牌子的话，先用「什么都录」的版本 [`blescan.py`](blescan.py)，把周围所有广播连同厂商数据一起记下来：

```python
"""用法：blescan.py <秒数> <输出文件>——记下周围所有广播，内容一变就记一行"""
import asyncio, sys, time, json
from bleak import BleakScanner

seconds = float(sys.argv[1]); out = open(sys.argv[2], "a")
seen = set()

def cb(dev, adv):
    rec = {
        "t": round(time.time(), 2),
        "name": adv.local_name or dev.name,
        "mfr": {str(k): v.hex() for k, v in (adv.manufacturer_data or {}).items()},  # 厂商数据
        "svc": list(adv.service_uuids or []),                                        # 服务 UUID
        "sdata": {k: v.hex() for k, v in (adv.service_data or {}).items()},          # 服务数据
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

找法：先**什么都不点**录 30 秒，记下周围本来就有的那些广播；再开始在 App 里换档，**新冒出来、而且跟着你换档一起变**的那一条就是它。看它的变化在哪一栏：

- **iPhone 发的**：iOS 不许 App 自定义厂商数据，指令只能藏在 `svc`（服务 UUID）或名字里，Love Spouse 就是这样
- **Android 发的**：多半在 `mfr`（厂商数据）里

找到之后，把它固定的那一段当第三个参数传给 `blelog.py`（比如 `blelog.py 600 cmds.jsonl 1a2b`），再照 2.4 节按顺序录一遍。如果变化在厂商数据里，在 `blescan.py` 的结果里对就行。

---

## 3. 读懂广播（Love Spouse 示例）

### 3.1 13 个 UUID 长什么样

```
08f9 2349 cbae d1c1 | XXXX 0bYY | 0d0c 0f0e 1110 1312 1514 1716 1918
└──── 固定的头 ────┘   └─指令─┘   └──────────── 固定的尾 ────────────┘
```

只有第 5、6 个在变（第 6 个的前半 `0b` 也不变），所以**一条指令其实就 3 个字节**。

### 3.2 三路的「停止」

| 哪一路 | 停止指令（第 5、6 个 UUID） |
|---|---|
| 动（主体） | `1f5e 0b0c` |
| 震（主体） | `982e 0b7f` |
| 吸（另一个零件） | `9c6e 0b3d` |

「动」和「震」可以同时开。

### 3.3 档位的规律

把 iPhone 广播换算回 Android 版用的三字节 `(a, b, c)`：

```
第 5 个 UUID = (b ^ 0x0A)(a ^ 0xBB)
第 6 个 UUID = 0b (c ^ 0x71)
```

在 `(a, b, c)` 这一层，**每一档 = 停止那条的 a、b、c 各 XOR 一个固定值**，三路用的是同一张表：

| 档位 | XOR (a, b, c) |
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

（a 的那一位 XOR 的就是档位数本身。）

为什么会有这么整齐的规律：Android 版的指令是「固定前缀 + 档位码」算 CRC16 之后再做两轮 whitening（和一串固定字节 XOR）得到的。CRC 和 XOR 都满足「输入差多少、输出就差固定的多少」，所以只改档位码时，结果总是差同一个 XOR 值。对照一下：「动 · 停止」换算回 Android 就是 `E5 15 7D`，和公开的 Android 表里 mode 0x00 的末三字节一字不差。

所以只要录到某一路的「停止」，1～9 档都能算出来。我录到的全表：

| 档位 | 动 | 震 | 吸 |
|---|---|---|---|
| 停 | `1f5e 0b0c` | `982e 0b7f` | `9c6e 0b3d` |
| 1 | `965f 0b1d` | `112f 0b6e` | `156f 0b2c` |
| 2 | `0d5c 0b2f` | `8a2c 0b5c` | `8e6c 0b1e` |
| 3 | `845d 0b3e` | `032d 0b4d` | `076d 0b0f` |
| 4 | `3b5a 0b4a` | `bc2a 0b39` | `b86a 0b7b` |
| 5 | `b25b 0b5b` | `352b 0b28` | `316b 0b6a` |
| 6 | `2958 0b69` | `ae28 0b1a` | `aa68 0b58` |
| 7 | `a059 0b78` | `2729 0b0b` | `2369 0b49` |
| 8 | `5756 0b80` | `d026 0bf3` | `d466 0bb1` |
| 9 | `de57 0b91` | `5927 0be2` | `5d67 0ba0` |

「吸」那一列的 1～9 档是按规律算的，和手机实际发出来的对比过，一字不差。

---

## 4. 重放验证（Mac 说）

用 Mac 自己当「手机」，把一条指令广播出去，玩具动了就说明读对了。

```bash
blevenv/bin/pip install pyobjc-framework-CoreBluetooth
```

核心就这几行：

```python
from CoreBluetooth import CBPeripheralManager, CBUUID, CBAdvertisementDataServiceUUIDsKey

HEAD = ["08f9", "2349", "cbae", "d1c1"]
TAIL = ["0d0c", "0f0e", "1110", "1312", "1514", "1716", "1918"]

def advertise(pm, code):              # code 例如 "b25b 0b5b"（动 · 5 档）
    uuids = [CBUUID.UUIDWithString_(u) for u in HEAD + code.split() + TAIL]
    pm.startAdvertising_({CBAdvertisementDataServiceUUIDsKey: uuids})
```

完整脚本（带蓝牙状态回调、输编号切档，内置上面的全表）见 [`replay.py`](replay.py)，同样要在**终端**里跑。

> 💡 **停止广播 ≠ 玩具停**。玩具会停在它最后听到的那一档，要停就发对应那一路的「停止」指令。
>
> 💡 实测「动」「震」用 Mac 重放都会理，「吸」那个零件对 Mac 的广播不理，用 iPhone 发就正常。猜测是 macOS 的广播间隔更慢，或者 UUID 被挪进了扫描回应包，那个零件更挑。

---

## 5. 接给 TA

能用电脑发指令之后，让 TA 控制就只剩「把一个按钮做成 TA 能调用的工具」：

- **最简单**：TA 能跑命令的话（比如 Claude Code），直接让 TA 调用重放脚本
- **离开电脑也能用**：iPhone 当广播端。在你自己的 App 里用 `CBPeripheralManager` 广播同样的 13 个 UUID，再开一个接口，TA 调接口 → 手机广播 → 玩具动

iPhone 上发一条指令只要这几行（Swift）：

```swift
import CoreBluetooth

let head = ["08F9", "2349", "CBAE", "D1C1"]
let tail = ["0D0C", "0F0E", "1110", "1312", "1514", "1716", "1918"]

// pm 是一个状态为 .poweredOn 的 CBPeripheralManager；code 例如 "B25B 0B5B"（动 · 5 档）
func advertise(_ pm: CBPeripheralManager, _ code: String) {
    let ids = (head + code.split(separator: " ").map(String.init) + tail).map { CBUUID(string: $0) }
    pm.stopAdvertising()
    pm.startAdvertising([CBAdvertisementDataServiceUUIDsKey: ids])
}
```

实测三路都能从 iPhone 控制，包括 Mac 发它不理的「吸」。

> ⚠️ iOS 的 App 退到后台后，广播的服务 UUID 会被系统挪进「溢出区」，有的玩具会听不到。要后台用，Info.plist 的后台模式里加上 `bluetooth-peripheral`，再自己实测一下前台 / 后台。

---

## 6. 安全提醒

广播**谁都听得到**。你在用的时候，附近任何人拿个扫描 App 都能看到、录下、重放。这是这类玩具本身的设计，不是这份教程造成的。仅供学习研究。

---

## 常见坑

| 现象 | 原因 |
|---|---|
| 脚本一跑就闪退、没报错 | 用了 Xcode 自带的 Python，换 Homebrew 的 |
| 什么都录不到 | 没在「终端」里跑，或者没给蓝牙权限 |
| 换档只录到一部分 | bleak 没改 `AllowDuplicates`（2.2 节） |
| 连上了玩具、写了指令不动 | 它不走连接，见第 1 节 |
| 发了「停止广播」玩具还在动 | 要发「停止」指令，不是停广播 |

---

## 致谢

- [Cami-Ose/muse-toy-broadcaster](https://github.com/Cami-Ose/muse-toy-broadcaster)（MIT）：MuSe / Love Spouse **Android 版**广播协议的逆向实现，包括厂商数据格式、CRC16 + 双层 whitening 和指令表。本文新补上的是 **iPhone 版**把指令编进服务 UUID 的格式，以及它和 Android 指令之间的换算
- [bleak](https://github.com/hbldh/bleak)：跨平台的 Python 蓝牙库
- [PyObjC](https://github.com/ronaldoussoren/pyobjc)：让 Python 调用 macOS 的 CoreBluetooth

## 许可

[MIT](LICENSE) © 2026 Tilia & Quercus
