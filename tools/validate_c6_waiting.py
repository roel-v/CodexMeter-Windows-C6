"""Check the real companion waiting/connected state and capture its display."""
import argparse
from pathlib import Path
import time
from serial_device import SerialSession, SerialToolError
from capture_c6_screen import capture

def validate(port_name, output, waiting, hold):
    output.mkdir(parents=True, exist_ok=True)
    with SerialSession(port_name) as port, (output / 'health.log').open('w') as log:
        def health():
            port.write_line('health')
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    line = port.read_line(1).decode(errors='replace')
                except SerialToolError:
                    continue
                if line.startswith('HEALTH '):
                    log.write(line + '\n')
                    log.flush()
                    return line
            raise RuntimeError('No health reply')
        deadline = time.monotonic() + 90
        while True:
            state = health()
            if f'waiting={int(waiting)}' in state and 'screen=1' in state:
                break
            if time.monotonic() >= deadline:
                raise AssertionError(state)
            time.sleep(1)
        capture(port, output / 'initial.png')
        print(state, flush=True)
        end = time.monotonic() + hold
        while time.monotonic() < end:
            state = health()
            assert f'waiting={int(waiting)}' in state and 'screen=1' in state, state
            assert 'wdt=1' in state, state
            time.sleep(min(10, max(0, end - time.monotonic())))
        capture(port, output / 'screen.png')
        print(state, flush=True)
        print(output / 'screen.png', flush=True)

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('port')
    p.add_argument('output', type=Path)
    p.add_argument('--waiting', action='store_true')
    p.add_argument('--hold', type=float, default=0)
    a = p.parse_args()
    validate(a.port, a.output, a.waiting, a.hold)
