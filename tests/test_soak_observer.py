from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from observe_mixed_soak import summarize, DEVICES


def samples():
    return [{"elapsed":t,"rss":100*1024*1024,
             "serial":{port:{"heap":{"i":100_000}} for port in DEVICES}}
            for t in range(0,15301,30)]


def test_stable_complete_soak():
    assert summarize(samples(),900,14400,[])["passed"]


def test_gap_or_truncated_run_cannot_pass():
    assert not summarize(samples(),900,14400,["Sleep gap"])["passed"]
    assert not summarize(samples()[:100],900,14400,[])["passed"]
    assert not summarize([samples()[30],samples()[-1]],900,14400,[])["passed"]


def test_host_growth_threshold_and_device_heap_loss():
    values=samples()
    for sample in values[-30:]:
        sample["rss"]+=21*1024*1024
    result=summarize(values,900,14400,[])
    assert not result["passed"] and any("RSS" in issue for issue in result["issues"])
    values=samples()
    for sample in values[-30:]:
        sample["serial"]["COM9"]["heap"]["i"]-=9000
    result=summarize(values,900,14400,[])
    assert not result["passed"] and any("COM9" in issue for issue in result["issues"])
