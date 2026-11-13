"""Ball-only reconnect/page-retention and explicit power-off regression check."""
import asyncio
import json
import time
from pathlib import Path
from bleak import BleakClient, BleakScanner
from serial_device import SerialSession
from validate_ball_ui import usage, activity, command, capture
from codexmeter.ble import BleIdentity
from codexmeter.payloads import Payload
from codexmeter.settings import IDENTITY_CHAR_UUID, RX_CHAR_UUID, TX_CHAR_UUID

def health():
    with SerialSession("COM9") as serial:
        serial.write_line("health")
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            text=serial.read_line(5).decode(errors="replace").strip()
            if text.startswith("HEALTH "):
                return dict(part.split("=",1) for part in text.split()[1:])
    raise RuntimeError("No health reply")

async def main():
    device=await BleakScanner.find_device_by_filter(lambda d,a:a.local_name=="CodexMeter-6867F4",timeout=15)
    assert device is not None
    out=Path(r"D:\build\CodexMeter\tmp\ball-phase4-captures")
    results=[]
    for attempt in range(2):
        async with BleakClient(device,timeout=15) as client:
            identity=BleIdentity.from_bytes(await client.read_gatt_char(IDENTITY_CHAR_UUID))
            assert identity.device_id=="codexmeter-6867f4697090"
            acks=asyncio.Queue()
            await client.start_notify(TX_CHAR_UUID,lambda c,data:acks.put_nowait(json.loads(bytes(data))))
            async def send(data):
                await client.write_gatt_char(RX_CHAR_UUID,Payload(data["k"],data).to_json_bytes(),response=True)
                while True:
                    ack=await asyncio.wait_for(acks.get(),5)
                    if "ack" in ack:
                        assert ack["ack"] is True
                        break
            await send(usage());await send(activity())
            if attempt==0:
                await asyncio.to_thread(command,"test_swipe")
                await asyncio.sleep(.3)
                await asyncio.to_thread(capture,out/"reconnect-before.png")
                await send(dict(v=1,k="control",cmd="screen",on=False,why="validation"))
            else:
                await send(dict(v=1,k="alert",id="off-check",title="Must remain off",body="Example",t=int(time.time())))
            await asyncio.sleep(.3)
            state=await asyncio.to_thread(health)
            assert state["screen"]=="0",state
            results.append(state)
            if attempt==1:
                await send(dict(v=1,k="control",cmd="screen",on=True,why="validation"))
                await asyncio.sleep(.3)
                await asyncio.to_thread(capture,out/"reconnect-after.png")
                assert (out/"reconnect-before.png").read_bytes()==(out/"reconnect-after.png").read_bytes()
                await asyncio.to_thread(command,"test_swipe")
                await asyncio.to_thread(command,"test_swipe")
        await asyncio.sleep(6)
        state=await asyncio.to_thread(health)
        assert state["waiting"]=="1",state
        if attempt==0: assert state["screen"]=="0",state
        results.append(state)
    print(json.dumps({"passed":True,"health":results},indent=2))

if __name__=="__main__":asyncio.run(main())
