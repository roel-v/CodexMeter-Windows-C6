import asyncio
import json
import time
from dataclasses import replace
import pytest
from codexmeter.ble import BleIdentity, BleIdentityError, BleState, BleTransport
from codexmeter.device_metadata import DeviceMetadata
from codexmeter.device_registry import DeviceConfig, DeviceRegistry
from codexmeter.multi_ble import DeviceManager, DeviceSlot, DeviceWorker, DiscoveryService
from codexmeter.payloads import Payload
from codexmeter.queueing import put_latest
from codexmeter.device_dialog import device_row


def config(index=1, model='spotpear_ball_v2'):
    return DeviceConfig(f'codexmeter-aabbcc{index:06x}', short_id='AABBCC', name='CodexMeter-AABBCC',
                        metadata=DeviceMetadata(model=model,protocol=1,capabilities=('brightness','rotation','screen')))


def manager(configs):
    return DeviceManager(configs,connect_timeout_sec=.1,disconnect_timeout_sec=.1,write_timeout_sec=.1,
                         ack_timeout_sec=.1,notify_timeout_sec=.1,healthcheck_interval_sec=1)


def test_registry_does_not_merge_duplicate_advertised_names(tmp_path):
    registry=DeviceRegistry(tmp_path/'devices.json')
    for i in range(4): registry.upsert(config(i))
    registry.save()
    assert len(DeviceRegistry.load(registry.path).devices)==4
    assert not config(0).matches(device_id=config(1).device_id,short_id='AABBCC')


def test_metadata_identity_and_legacy():
    base={'device_id':config().device_id,'short_id':'AABBCC','name':'CodexMeter-AABBCC'}
    assert BleIdentity.from_bytes(json.dumps(base).encode()).metadata.compatibility=='legacy'
    parsed=BleIdentity.from_bytes(json.dumps(dict(base,**config().metadata.to_json())).encode())
    assert parsed.metadata.model=='spotpear_ball_v2'
    with pytest.raises(BleIdentityError): BleIdentity.from_bytes(b' '*513)
    with pytest.raises(BleIdentityError): BleIdentity.from_bytes(json.dumps(dict(base,protocol=True)).encode())


def test_incompatible_worker_is_independent():
    first,second=DeviceSlot(config(1)),DeviceSlot(config(2))
    worker=DeviceWorker(first,DiscoveryService(),BleTransport())
    identity=BleIdentity(first.config.device_id,'AABBCC','CodexMeter-AABBCC',DeviceMetadata(protocol=2))
    with pytest.raises(BleIdentityError): worker._validate_identity(identity)
    assert first.status(now=0)['compatibility']=='incompatible'
    assert second.config.metadata.compatible


def test_targeted_settings_and_full_queue_do_not_block_other_displays():
    async def run():
        m=manager([config(i, 'spotpear_ball_v2' if i%2 else 'waveshare_c6_amoled_216') for i in range(4)])
        for i in range(32): await m.slots[0].queue.put(Payload('alert',{'id':i}))
        for command,value in [('brightness',30),('rotation',90)]:
            await m.control_device(dict(device_id=config(1).device_id,command=command,value=value))
        assert m.slots[1].queue.qsize()==2
        assert not m.slots[2].state.desired_settings
        payload=Payload('activity',{'k':'activity','run':3})
        await asyncio.wait_for(m.broadcast(payload),.1)
        assert all(s.state.last_activity is payload for s in m.slots)
        assert all(s.queue.qsize()<=32 for s in m.slots)
        assert set(m.slots[1].state.desired_settings)=={'brightness','rotation'}
    asyncio.run(run())


def test_controls_fail_closed_for_unsupported_or_disabled_device():
    async def run():
        m=manager([replace(config(),metadata=DeviceMetadata()),replace(config(2),enabled=False)])
        with pytest.raises(ValueError): await m.control_device(dict(device_id=config().device_id,command='rotation',value=90))
        with pytest.raises(ValueError): await m.control_device(dict(device_id=config(2).device_id,command='screen',value=True))
        with pytest.raises(ValueError): await m.control_device(dict(device_id=config().device_id,command='screen',value='true'))
    asyncio.run(run())


def test_old_ack_and_queued_snapshot_do_not_replace_new_desired_state():
    state=BleState(); old=Payload('usage',{'t':1}); new=Payload('usage',{'t':2})
    BleTransport.remember_desired(new,state)
    BleTransport._remember_payload(old,state)
    assert state.last_usage is new
    assert not BleTransport()._should_write_payload(old,state)
    assert BleTransport()._should_write_payload(new,state)


def test_expired_alert_is_not_replayed():
    transport=BleTransport();state=BleState()
    assert not transport._should_write_payload(Payload('alert',{'t':time.time()-61}),state)
    assert transport._should_write_payload(Payload('alert',{'t':time.time()}),state)


def test_control_queue_keeps_distinct_settings_but_coalesces_same_setting():
    async def run():
        q=asyncio.Queue(maxsize=4)
        for cmd,value in [('brightness',50),('rotation',90),('brightness',70)]:
            await put_latest(q,Payload('control',{'cmd':cmd,'value':value}))
        assert [(q.get_nowait().data) for _ in range(q.qsize())]==[{'cmd':'rotation','value':90},{'cmd':'brightness','value':70}]
    asyncio.run(run())


def test_device_row_reports_incompatible_not_reconnecting():
    row=device_row({'device_id':'x','compatibility':'incompatible','last_error':'Unsupported protocol'})
    assert row[3]=='Incompatible protocol'
