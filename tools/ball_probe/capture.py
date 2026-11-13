"""Capture only this diagnostic firmware's serial output and isolated BLE status."""
import asyncio, json, time
from pathlib import Path
import serial
from serial.tools.list_ports import comports
from bleak import BleakScanner, BleakClient

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '.plans/1_planning/2026-11-13_spotpear-ball-codexmeter/hardware'
IDENTITY = '90:70:69:F4:67:68'

def capture():
    port = next(p.device for p in comports() if p.serial_number == IDENTITY)
    lines=[]
    connection=serial.Serial()
    connection.port=port; connection.baudrate=115200; connection.timeout=1
    connection.dtr=False; connection.rts=False; connection.open()
    with connection:
        end=time.monotonic()+30
        while time.monotonic()<end:
            line=connection.readline().decode('utf-8',errors='replace').strip()
            if line.startswith(('{','TOUCH ','BUTTON ','START ','I2C ','TOUCH_CONFIG ','TOUCH_DIAG ')):
                lines.append(line)
    (OUT/'probe-serial.log').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    samples=[json.loads(line) for line in lines if line.startswith('{')]
    return {'samples':len(samples),'first':samples[0] if samples else None,'last':samples[-1] if samples else None}

async def bluetooth():
    device=await BleakScanner.find_device_by_filter(lambda d,a: a.local_name=='BallProbe-F46768',timeout=15)
    if not device: return {'error':'probe not discovered'}
    readings=[]
    for attempt in range(2):
        async with BleakClient(device,timeout=15) as client:
            value=await client.read_gatt_char('c631f467-6768-4000-8000-000000000002')
            readings.append(json.loads(value.decode()))
        await asyncio.sleep(2)
    return {'connections':len(readings),'readings':readings}

async def main():
    global OUT
    OUT = OUT / time.strftime('%Y%m%d-%H%M%S')
    OUT.mkdir(parents=True, exist_ok=True)
    results=await asyncio.gather(asyncio.to_thread(capture),bluetooth(),return_exceptions=True)
    result={name:(str(value) if isinstance(value,Exception) else value) for name,value in zip(('serial','bluetooth'),results)}
    (OUT/'probe-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__': asyncio.run(main())
