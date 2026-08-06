# Pybricks Remote for iOS

A native SwiftUI remote for a Pybricks-powered SPIKE Prime hub. It mirrors the
working PC/Bleak protocol:

- scans for the Pybricks GATT service `c5f50001-8280-46da-89f4-6d8051e4aeef`;
- writes `0x06 + fwd`, `rev`, or `stp` to the command/event characteristic;
- receives the Pybricks stdout event (`0x01`) and waits for `rdy` / displays
  `ack:<command>`.

## Open and run in Xcode

1. Open `PybricksRemote.xcodeproj` in Xcode.
2. If Xcode asks, accept its license agreement and allow any recommended project
   setting updates.
3. Select the **PybricksRemote** target, then **Signing & Capabilities**. Choose
   your Apple Development Team and, if needed, replace
   `com.example.PybricksRemote` with a unique bundle identifier.
4. Select your connected iPhone or iPad as the run destination, then press
   **Run** (⌘R). The iOS Simulator has no Bluetooth LE hardware.

On the first run, grant the Bluetooth permission prompt. Start the hub program
and wait for the app to show **Ready** before tapping a motor control.

## Required hub program

The app expects the same fixed-length hub protocol as the PC program: send
`rdy` before input, then `ack:` followed by the 3-byte command after input.

```python
from pybricks.pupdevices import Motor
from pybricks.parameters import Port
from pybricks.tools import wait
from usys import stdin, stdout
from uselect import poll

motor = Motor(Port.A)
keyboard = poll()
keyboard.register(stdin)

while True:
    stdout.buffer.write(b"rdy")
    while not keyboard.poll(0):
        wait(10)

    cmd = stdin.buffer.read(3)
    if cmd == b"fwd":
        motor.dc(50)
    elif cmd == b"rev":
        motor.dc(-50)
    else:
        motor.stop()
    stdout.buffer.write(b"ack:" + cmd)
```

The app parser intentionally handles a combined notification such as
`ack:fwdrdy`, which is normal for this small unframed demo protocol.
