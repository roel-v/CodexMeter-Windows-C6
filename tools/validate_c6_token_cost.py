"""Hardware checks for token pages; run with the companion stopped.

Serial gesture injection verifies the UI, not a human finger or the touch surface.
The separate touch_status command checks controller presence and rotation geometry.
"""
import argparse
import json
import re
import time
from pathlib import Path
from serial_device import SerialSession, SerialToolError
from capture_c6_screen import capture


def validate(port_name, output):
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    with SerialSession(port_name) as port:
        def command(text, marker):
            time.sleep(.15)
            port.write_line(text)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    line = port.read_line(.5).decode(errors='replace')
                except SerialToolError:
                    continue
                if marker in line:
                    if text.startswith('logs '):
                        # Consume the complete dump, avoiding stale matches next time.
                        while 'LOGS_END' not in port.read_line(2).decode(errors='replace'):
                            pass
                    return line
            raise RuntimeError(f'No response: {text[:40]}')
        port.write_line('settings_close')
        command('test_ui_on', 'TEST_UI on')
        command('theme classic_tasks', 'THEME_OK')
        touch = command('touch_status', 'TOUCH ')
        assert 'ready=1' in touch and 'geometry=1' in touch, touch
        results['touch'] = touch
        payload = {'v': 1, 'k': 'usage', 'src': 'codex', 'd7': 94, 'd7r': int(time.time()) + 600000,
                   'td': 92000000, 't7': 644000000, 'st': 'ok', 't': int(time.time()),
                   'b0': [10000000, 80000000, 2000000, 2000, 800, 2000, 0, 0],
                   'b7': [70000000, 560000000, 14000000, 14000, 5600, 14000, 0, 0]}
        command(json.dumps(payload, separators=(',', ':')), 'usage h5=')
        command(json.dumps({'k':'activity','run':2,'wait':0,'done':3,'chats':True}), 'activity run=')
        time.sleep(.3)
        capture(port, output / 'dashboard.png')
        command('test_swipe', 'token page=1')
        capture(port, output / 'details-today.png')
        command('test_tap_week', 'week=1')
        capture(port, output / 'details-week.png')
        payload['b0'][6] = 1
        command(json.dumps(payload, separators=(',', ':')), 'usage h5=')
        command('test_tap_today', 'week=0')
        capture(port, output / 'details-partial.png')
        results['heaps'] = []
        for i in range(12):
            command('test_swipe', 'token page=')
            port.write_line('lvheap')
            time.sleep(.2)
            results['heaps'].append(command('logs 3', 'lv_mem serial '))
        # Even number of toggles leaves details visible; return to dashboard.
        command('test_swipe', 'token page=0')
        for r in range(4):
            command(f'rotate {r}', f'ROTATION {r}')
            time.sleep(1)
            assert 'geometry=1' in command('touch_status', 'TOUCH ')
        command('rotate auto', 'orientation auto=1')
        results['health'] = command('health', 'HEALTH ')
        assert 'wdt=1' in results['health']
        free = [int(re.search(r' f=(\d+)', line)[1]) for line in results['heaps']]
        assert min(free) > 12000, free
        assert free[-1] >= free[0] - 2048, free
        results['physical_finger_test'] = 'Requires user swipe/tap; serial injection is not physical input.'
        command('test_ui_off', 'TEST_UI off')
    (output / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print('C6 token pages, period selection, partial costs, heap stability and rotation geometry passed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('port')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    validate(args.port, args.output)
