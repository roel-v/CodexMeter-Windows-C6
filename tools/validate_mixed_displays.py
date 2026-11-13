"""Exercise the production DeviceManager against the identified C6 and Ball.

Uses synthetic examples and real BLE disconnects, never resets either board or
the Bluetooth radio. Stop the installed companion before running. No registry
writes or restart watchdog; the caller restores/starts the companion afterward.
"""
import argparse
import asyncio
import json
import logging
import time
from pathlib import Path
from codexmeter.device_registry import DeviceConfig
from codexmeter.multi_ble import DeviceManager
from codexmeter.payloads import Payload
from validate_ball_ui import usage, activity

CONFIGS=[
    DeviceConfig("codexmeter-00e216f16e20",short_id="00E216",alias="Waveshare C6",name="CodexMeter-00E216"),
    DeviceConfig("codexmeter-6867f4697090",short_id="6867F4",alias="Spotpear Ball",name="CodexMeter-6867F4"),
]
async def run(output):
    output.mkdir(parents=True,exist_ok=True)
    manager=DeviceManager(CONFIGS,connect_timeout_sec=15,disconnect_timeout_sec=5,
        write_timeout_sec=10,ack_timeout_sec=10,notify_timeout_sec=5,healthcheck_interval_sec=45)
    clients={}
    for index,worker in enumerate(manager._workers):
        original=worker.transport._create_client
        def factory(target,index=index,original=original):
            client=original(target);clients[index]=client;return client
        worker.transport._create_client=factory
    stop=asyncio.Event()
    runner=asyncio.create_task(manager.run(stop))
    async def publish():
        while not stop.is_set():
            for data in (usage(),activity()):
                await manager.broadcast(Payload(data["k"],data))
            await asyncio.sleep(3)
    publisher=asyncio.create_task(publish())
    results={"physical_devices":2,"cycles":[]}
    async def wait_ready(deadline,after=None):
        while time.monotonic()<deadline:
            if runner.done(): await runner
            if all(s.state.connected and s.state.last_ack_at and
                   time.monotonic()-s.state.last_ack_at<6 and
                   (after is None or s.state.last_ack_at>after) for s in manager.slots):
                return
            await asyncio.sleep(.2)
        raise AssertionError({"connection_timeout":manager.status()})
    try:
        await wait_ready(time.monotonic()+90)
        for slot,config in zip(manager.slots,CONFIGS):
            assert slot.state.observed_device_id==config.device_id
        results["initial"]=manager.status()
        (output/"initial.json").write_text(json.dumps(results["initial"],indent=2))
        print("Both physical displays connected and acknowledging the same examples.",flush=True)
        for target in range(2):
            for cycle in range(10):
                await wait_ready(time.monotonic()+15)
                started=time.monotonic()
                other=manager.slots[1-target]
                other_connection=other.state.last_connected_at
                await clients[target].disconnect()
                deadline=started+60
                max_healthy_age=0.
                while time.monotonic()<deadline:
                    now=time.monotonic()
                    age=now-(other.state.last_ack_at or 0)
                    max_healthy_age=max(max_healthy_age,age)
                    assert other.state.connected and other.state.last_connected_at==other_connection,manager.status()
                    assert age<=6,{"healthy_ack_gap":age,"status":manager.status()}
                    state=manager.slots[target].state
                    if state.connected and (state.last_connected_at or 0)>started and (state.last_ack_at or 0)>started:
                        break
                    await asyncio.sleep(.1)
                else: raise AssertionError({"reconnect_timeout":manager.status()})
                entry={"target":CONFIGS[target].alias,"cycle":cycle+1,
                    "reconnected_seconds":round(time.monotonic()-started,3),
                    "healthy_max_ack_age":round(max_healthy_age,3)}
                results["cycles"].append(entry)
                print(json.dumps(entry),flush=True)
                await asyncio.sleep(3)
        results["final"]=manager.status()
        results["passed"]=True
    except BaseException as exc:
        results["passed"]=False;results["error"]=repr(exc);results["failure_status"]=manager.status()
        raise
    finally:
        stop.set();publisher.cancel()
        await asyncio.gather(publisher,return_exceptions=True)
        await asyncio.wait_for(runner,20)
        (output/"results.json").write_text(json.dumps(results,indent=2))
    return results

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(run(args.output))
