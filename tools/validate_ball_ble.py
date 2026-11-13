"""Bounded Ball-only BLE validation; does not modify the companion registry."""
import asyncio
import json
from pathlib import Path
from bleak import BleakScanner, BleakClient
from codexmeter.ble import BleIdentity
from codexmeter.settings import IDENTITY_CHAR_UUID, RX_CHAR_UUID, TX_CHAR_UUID
from codexmeter.payloads import Payload

async def main():
    device=await BleakScanner.find_device_by_filter(lambda d,a:a.local_name=='CodexMeter-6867F4',timeout=15)
    if not device: raise RuntimeError('Ball not found')
    results=[]
    for attempt in range(2):
        async with BleakClient(device,timeout=15) as client:
            raw=await client.read_gatt_char(IDENTITY_CHAR_UUID)
            identity=BleIdentity.from_bytes(raw)
            assert identity.device_id=='codexmeter-6867f4697090'
            assert identity.metadata.model=='spotpear_ball_v2'
            assert identity.metadata.width==240 and identity.metadata.height==240
            acks=asyncio.Queue()
            await client.start_notify(TX_CHAR_UUID,lambda c,data:acks.put_nowait(json.loads(bytes(data))))
            for command,value in [('brightness',40),('rotation',90),('rotation',0),('brightness',60)]:
                data={'v':1,'k':'control','cmd':command,'value':value}
                await client.write_gatt_char(RX_CHAR_UUID,Payload('control',data).to_json_bytes(),response=True)
                ack=await asyncio.wait_for(acks.get(),5)
                assert ack.get('ack') is True,ack
            results.append({'identity_bytes':len(raw),'metadata':identity.metadata.to_json(),'settings_acks':4})
        await asyncio.sleep(1)
    print(json.dumps(results,indent=2))

if __name__=='__main__':asyncio.run(main())
