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
