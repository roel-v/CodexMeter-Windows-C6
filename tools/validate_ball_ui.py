"""Ball-only UI validation with synthetic, explicitly labelled example data.

Captures real framebuffers; optional bounded serving keeps examples available for
physical review. Never registers devices or controls the installed companion/C6.
"""
import argparse
import asyncio
import json
import time
from pathlib import Path

from bleak import BleakClient, BleakScanner
from capture_screenshot import capture_rgb565le, rgb565le_to_png
from serial_device import SerialSession
from codexmeter.ble import BleIdentity
from codexmeter.payloads import Payload
from codexmeter.settings import IDENTITY_CHAR_UUID, RX_CHAR_UUID, TX_CHAR_UUID

def command(text):
    with SerialSession("COM9") as serial:
        serial.write_line(text)

def capture(path):
    width,height,data=capture_rgb565le("COM9")
    assert (width,height)==(240,240)
    path.write_bytes(rgb565le_to_png(width,height,data))

def usage(**changes):
    now=int(time.time())
    data=dict(v=1,k="usage",t=now,st="ok",h5=-1,d7=69,d7r=now+3*86400+4*3600+1800,
              td=18600000,t7=236000000,
              b0=[1200000,16800000,600000,360,420,900,0,0],
              b7=[18000000,210000000,8000000,5400,5250,12000,0,0])
    data.update(changes)
    return data

def activity(**changes):
    data=dict(v=1,k="activity",t=int(time.time()),run=3,wait=2,done=4,chats=True)
    data.update(changes)
    return data

async def main(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    device=await BleakScanner.find_device_by_filter(lambda d,a:a.local_name=="CodexMeter-6867F4",timeout=15)
    if device is None: raise RuntimeError("Ball not found")
    async with BleakClient(device,timeout=15) as client:
        identity=BleIdentity.from_bytes(await client.read_gatt_char(IDENTITY_CHAR_UUID))
        assert identity.device_id=="codexmeter-6867f4697090"
        assert identity.metadata.model=="spotpear_ball_v2"
        acks=asyncio.Queue()
        await client.start_notify(TX_CHAR_UUID,lambda c,data:acks.put_nowait(json.loads(bytes(data))))
        async def send(data):
            await client.write_gatt_char(RX_CHAR_UUID,Payload(data["k"],data).to_json_bytes(),response=True)
            while True:
                ack=await asyncio.wait_for(acks.get(),5)
                if "ack" in ack:
                    assert ack["ack"] is True,ack
                    break
        async def shot(name):
            await asyncio.sleep(.25)
            await asyncio.to_thread(capture,out/(name+".png"))
        await send(usage());await send(activity())
        if not args.serve_only:
            for page in range(3):
                await send(activity())
                await shot(f"example-{page+1}")
                await send(dict(v=1,k="alert",id=f"ball-validation-{page}-{int(time.time())}",
                                title="Task complete!",body="Example completion notification. Your selected page will return.",t=int(time.time())))
                await asyncio.sleep(1.5)
                await shot(f"alert-{page+1}")
                await asyncio.sleep(8)
                await send(activity())
                await shot(f"restored-{page+1}")
                assert (out/f"example-{page+1}.png").read_bytes()==(out/f"restored-{page+1}.png").read_bytes()
                await asyncio.to_thread(command,"test_swipe")
            await send(usage(d7=100,d7r=int(time.time())+86399))
            await send(activity(run=999,wait=999,done=999))
            await shot("boundary-100-tasks999")
            await send(usage(d7=0,d7r=int(time.time())-1))
            await send(activity(run=1000,wait=1000,done=1000))
            await shot("boundary-zero-expired")
            await send(usage(d7=-1,b0=[],b7=[]))
            await shot("boundary-unknown-quota")
            await asyncio.to_thread(command,"test_swipe")
            await shot("boundary-missing-breakdown")
            await send(usage(b0=[2**64-1]*6+[1,1],td=2**64-1))
            await shot("boundary-large-partial")
            await send(usage(st="stale"))
            await shot("boundary-stale")
            await asyncio.to_thread(command,"test_swipe")
            await asyncio.to_thread(command,"test_swipe")
            for rotation in (90,180,270,0):
                await send(dict(v=1,k="control",cmd="rotation",value=rotation))
                await shot(f"rotation-{rotation}")
            await send(usage());await send(activity())
        print(json.dumps({"device":identity.device_id,"examples":str(out),"serve_minutes":args.serve_minutes}),flush=True)
        deadline=time.monotonic()+args.serve_minutes*60
        while time.monotonic()<deadline:
            await send(usage());await send(activity())
            await asyncio.sleep(3)
    await asyncio.sleep(6)
    await asyncio.to_thread(capture,out/"waiting-after-disconnect.png")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True)
    parser.add_argument("--serve-minutes",type=float,default=0)
    parser.add_argument("--serve-only",action="store_true")
    asyncio.run(main(parser.parse_args()))
