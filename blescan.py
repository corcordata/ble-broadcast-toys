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
