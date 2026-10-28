"""Mac 当手机：把一条指令按 Love Spouse iPhone 版的格式广播出去，看玩具动不动。

必须在「终端」App（Terminal.app）里跑，才有蓝牙权限：
    blevenv/bin/pip install bleak pyobjc-framework-CoreBluetooth
    blevenv/bin/python replay.py

输入编号回车 = 开始广播那一条（换一条直接输新编号）；s = 停止广播；q = 退出。
停止广播不等于玩具停：玩具会停在最后听到的那一档，要停就放那一路的「停止」。
"""
import sys
import threading
import time

import objc
from CoreBluetooth import CBPeripheralManager, CBUUID, CBAdvertisementDataServiceUUIDsKey
from Foundation import NSObject, NSRunLoop, NSDate

HEAD = ["08f9", "2349", "cbae", "d1c1"]
TAIL = ["0d0c", "0f0e", "1110", "1312", "1514", "1716", "1918"]

# (编号, 第 5、6 个 UUID, 是什么)：Love Spouse 三路的全表，规律见 README 第 3 节。
# 换别的玩具就把这张表和上面的 HEAD / TAIL 换成你自己录到的。
CODES = [
    ("0", "1f5e 0b0c", "动 · 停止"),
    ("1", "965f 0b1d", "动 · 1档"), ("2", "0d5c 0b2f", "动 · 2档"), ("3", "845d 0b3e", "动 · 3档"),
    ("4", "3b5a 0b4a", "动 · 4档"), ("5", "b25b 0b5b", "动 · 5档"), ("6", "2958 0b69", "动 · 6档"),
    ("7", "a059 0b78", "动 · 7档"), ("8", "5756 0b80", "动 · 8档"), ("9", "de57 0b91", "动 · 9档"),
    ("10", "982e 0b7f", "震 · 停止"),
    ("11", "112f 0b6e", "震 · 1档"), ("12", "8a2c 0b5c", "震 · 2档"), ("13", "032d 0b4d", "震 · 3档"),
    ("14", "bc2a 0b39", "震 · 4档"), ("15", "352b 0b28", "震 · 5档"), ("16", "ae28 0b1a", "震 · 6档"),
    ("17", "2729 0b0b", "震 · 7档"), ("18", "d026 0bf3", "震 · 8档"), ("19", "5927 0be2", "震 · 9档"),
    ("20", "9c6e 0b3d", "吸 · 停止"),
    ("21", "156f 0b2c", "吸 · 1档"), ("22", "8e6c 0b1e", "吸 · 2档"),
    ("23", "076d 0b0f", "吸 · 3档"), ("24", "b86a 0b7b", "吸 · 4档"),
    ("25", "316b 0b6a", "吸 · 5档"), ("26", "aa68 0b58", "吸 · 6档"),
    ("27", "2369 0b49", "吸 · 7档"), ("28", "d466 0bb1", "吸 · 8档"),
    ("29", "5d67 0ba0", "吸 · 9档"),
]


class Delegate(NSObject):
    def init(self):
        self = objc.super(Delegate, self).init()
        self.ready = False
        return self

    def peripheralManagerDidUpdateState_(self, pm):
        self.ready = pm.state() == 5      # CBManagerStatePoweredOn
        print("蓝牙准备好了" if self.ready else f"蓝牙状态 {pm.state()}（5 才是开着）", flush=True)

    def peripheralManagerDidStartAdvertising_error_(self, pm, err):
        if err:
            print("广播失败：", err, flush=True)


def main():
    delegate = Delegate.alloc().init()
    pm = CBPeripheralManager.alloc().initWithDelegate_queue_(delegate, None)
    wanted = {"code": None, "stop": False}

    def ask():
        print("\n".join(f"  {n:>2}  {c}  {label}" for n, c, label in CODES), flush=True)
        print("输编号回车开始放；s 停止广播；q 退出", flush=True)
        for line in sys.stdin:
            cmd = line.strip()
            if cmd == "q":
                wanted["stop"] = True
                return
            wanted["code"] = cmd

    threading.Thread(target=ask, daemon=True).start()
    current = None
    while not wanted["stop"]:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
        cmd = wanted["code"]
        if cmd is None or not delegate.ready:
            continue
        wanted["code"] = None
        if cmd == "s":
            pm.stopAdvertising()
            current = None
            print("停止广播了", flush=True)
            continue
        hit = next((c for c in CODES if c[0] == cmd), None)
        if not hit:
            print("没有这个编号", flush=True)
            continue
        if current:
            pm.stopAdvertising()
            time.sleep(0.2)
        uuids = [CBUUID.UUIDWithString_(u) for u in HEAD + hit[1].split() + TAIL]
        pm.startAdvertising_({CBAdvertisementDataServiceUUIDsKey: uuids})
        current = hit
        print(f"{time.strftime('%H:%M:%S')} 在放 {hit[0]}：{hit[1]}（{hit[2]}）", flush=True)
    pm.stopAdvertising()


main()
