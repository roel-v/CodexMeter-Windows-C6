"""Bounded, read-only soak observer for a running two-display companion.

Never starts/restarts the app or resets hardware. Stores health/heap/queue/process
metrics only, not task text or usage content. PC sleep/gaps invalidate the run.
"""
import argparse
import asyncio
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import re
import statistics
import time

from codexmeter.events import send_event
from codexmeter.settings import APP_DIR
from serial_device import SerialSession, SerialToolError

DEVICES={"COM6":"codexmeter-00e216f16e20","COM9":"codexmeter-6867f4697090"}

def rss_bytes(pid):
    class Counters(ctypes.Structure):
        _fields_=[("cb",wintypes.DWORD),("PageFaultCount",wintypes.DWORD),
                  *[(name,ctypes.c_size_t) for name in ("PeakWorkingSetSize","WorkingSetSize",
                    "QuotaPeakPagedPoolUsage","QuotaPagedPoolUsage","QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage","PagefileUsage","PeakPagefileUsage")]]
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    psapi=ctypes.WinDLL("psapi",use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    handle=kernel.OpenProcess(0x1010,False,pid)
    if not handle: raise ctypes.WinError(ctypes.get_last_error())
    try:
        value=Counters();value.cb=ctypes.sizeof(value)
        if not psapi.GetProcessMemoryInfo(handle,ctypes.byref(value),value.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return value.WorkingSetSize
    finally: kernel.CloseHandle(handle)

def device_health(port,expected):
    with SerialSession(port) as serial:
        serial.write_line("identity")
        serial.write_line("heap")
        serial.write_line("health")
        result={}
        deadline=time.monotonic()+6
        while time.monotonic()<deadline:
            try: line=serial.read_line(1).decode(errors="replace").strip()
            except SerialToolError: continue
            if expected in line and "device_id" in line: result["identity"]=expected
            if "heap serial " in line:
                match=re.match(r"LOG \d+ (\d+) \w+ heap serial (.*)",line)
                if match:
                    result["uptime_ms"]=int(match[1])
                    result["heap"]={k:int(v) for k,v in (p.split("=") for p in match[2].split())}
            if line.startswith("HEALTH "):
                result["health"]={k:int(v) for k,v in (p.split("=") for p in line.split()[1:])}
            if len(result)==4: return result
        raise RuntimeError(f"Incomplete health from {port}: {sorted(result)}")

def summarize(samples,warmup,duration,issues):
    measured=[s for s in samples if s.get("elapsed",0)>=warmup and "rss" in s and "serial" in s]
    result={"passed":False,"samples":len(samples),"measured_samples":len(measured),"issues":issues[:100]}
    if not measured: return result
    first=[s for s in measured if s["elapsed"]<warmup+900]
    last=[s for s in measured if s["elapsed"]>=warmup+duration-900]
    if len(measured)<duration/30*.9 or len(first)<27 or len(last)<27:
        result["issues"].append("Insufficient baseline/final window or overall sampling coverage");return result
    rss_first=statistics.median(s["rss"] for s in first)
    rss_last=statistics.median(s["rss"] for s in last)
    result["rss"]={"first_median":rss_first,"last_median":rss_last,"growth":rss_last-rss_first}
    if rss_last-rss_first>max(20*1024*1024,.1*rss_first):
        result["issues"].append("Host RSS growth exceeds acceptance limit")
    result["heap"]={}
    for port in DEVICES:
        initial=statistics.median(s["serial"][port]["heap"]["i"] for s in first)
        final=statistics.median(s["serial"][port]["heap"]["i"] for s in last)
        result["heap"][port]={"first_median":initial,"last_median":final,"loss":initial-final}
        if initial-final>max(8192,.05*initial): result["issues"].append(f"{port} heap loss exceeds limit")
    result["passed"]=not result["issues"] and measured[-1]["elapsed"]>=warmup+duration-35
    return result

async def monitor(args):
    args.output.mkdir(parents=True,exist_ok=True)
    samples=[];issues=[];previous=None;run_id=None;offline={}
    started=time.time();ends=started+args.warmup+args.duration
    with (args.output/"samples.jsonl").open("w",encoding="utf-8") as stream:
        while time.time()<=ends:
            tick=time.time()
            sample={"utc_epoch":tick,"elapsed":tick-started}
            try:
                if previous and tick-previous["utc_epoch"]>75: issues.append("Sleep or observation gap over 75 seconds")
                response=await asyncio.wait_for(send_event({"type":"ping"}),10)
                devices=response.get("ble",{}).get("devices",[])
                expected=set(DEVICES.values())
                assert {d["device_id"] for d in devices if d.get("enabled")}==expected,"Expected exactly the two test displays"
                sample["ble"]=[{k:d.get(k) for k in ("device_id","connected","queue_depth","last_ack_age_sec",
                    "consecutive_failures","last_error")} for d in devices]
                diagnostic=json.loads((APP_DIR/"diagnostics"/"last-run.json").read_text())
                sample["pid"]=diagnostic["pid"];sample["run_id"]=diagnostic["run_id"]
                if run_id is None:run_id=sample["run_id"]
                elif run_id!=sample["run_id"]:issues.append("Companion process changed during soak")
                sample["heartbeat_ages"]={k:tick-diagnostic.get(k,0) for k in ("last_bridge_heartbeat","last_ui_heartbeat")}
                if any(v>90 for v in sample["heartbeat_ages"].values()):issues.append("Stale companion heartbeat")
                sample["rss"]=rss_bytes(sample["pid"])
                sample["serial"]={}
                for port,identity in DEVICES.items():
                    sample["serial"][port]=await asyncio.to_thread(device_health,port,identity)
                    if previous and port in previous.get("serial",{}):
                        before=previous["serial"][port]["uptime_ms"];now=sample["serial"][port]["uptime_ms"]
                        if now<before and before<0xffff0000:issues.append(f"{port} unexpected reset")
                for device in devices:
                    ident=device["device_id"]
                    healthy=device.get("connected") and device.get("last_ack_age_sec") is not None and device["last_ack_age_sec"]<=120
                    if healthy:offline.pop(ident,None)
                    else:
                        offline.setdefault(ident,tick)
                        if tick-offline[ident]>60:issues.append(f"{ident} unrecovered delivery outage")
                    if device.get("queue_depth",0)>32:issues.append(f"{ident} unbounded queue")
            except Exception as exc:
                sample["error"]=repr(exc);issues.append(f"Observation failed: {exc}")
            samples.append(sample);stream.write(json.dumps(sample)+"\n");stream.flush();previous=sample
            (args.output/"progress.json").write_text(json.dumps({"elapsed":sample["elapsed"],"samples":len(samples),
                "issues":len(issues),"finish_epoch":ends},indent=2))
            await asyncio.sleep(max(0,30-(time.time()-tick)))
    result=summarize(samples,args.warmup,args.duration,issues)
    (args.output/"result.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    return 0 if result["passed"] else 1

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output",type=Path)
    parser.add_argument("--warmup",type=float,default=900)
    parser.add_argument("--duration",type=float,default=14400)
    args=parser.parse_args()
    if args.duration<1800 or args.warmup<0:parser.error("Require at least 30 minutes of measured observation")
    raise SystemExit(asyncio.run(monitor(args)))
