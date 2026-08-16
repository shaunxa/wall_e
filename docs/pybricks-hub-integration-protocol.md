# Pybricks Hub Protocol and Command Set

**Status:** Draft v1.0 — 16 August 2026  
**Scope:** SPIKE Prime / Pybricks Wall‑E companion  
**Audience:** iOS, Android, and Raspberry Pi Python web-app or native-app developers

## 1. Purpose and decision

This document defines the shared app-to-hub contract for new clients. It standardizes the newline-delimited Wall‑E companion protocol used by the Raspberry Pi Python web app and the hub program.

New iOS and Android implementations should adopt this protocol so every client sends the same commands, parses the same events, and preserves the robot’s safety behavior.

> **Normative choice:** Use the current line protocol (`READY`, `ACK`, `ERR`, `SAFE`, and `TEL`), not the older fixed three-byte iOS demo protocol. The old `fwd`, `rev`, `stp`, `rdy`, and `ack:` exchange is legacy-only and must not be used for new integrations.

## 2. Architecture and responsibilities

| Layer | Responsibility | Implementation rule |
| --- | --- | --- |
| Mobile or web client | Scan, select, connect, subscribe, issue supported commands, and render state. | Never bypass hub safety rules or assume a command succeeded without an `ACK` or safety event. |
| BLE transport | Carries Pybricks command input and stdout notifications. | One active host connection to the hub at a time. |
| Hub program | Parses complete lines, controls motors, owns safety stops, and emits telemetry. | It is the authority for obstacle, touch, timeout, and speed limits. |
| Optional web API | Provides a deliberately limited UI-facing control surface. | Map actions to allow-listed hub commands; do not expose arbitrary command input. |

## 3. BLE transport contract

| Item | Value / behavior |
| --- | --- |
| Advertising filter | Pybricks service UUID: `c5f50001-8280-46da-89f4-6d8051e4aeef` |
| Command/event characteristic | `c5f50002-8280-46da-89f4-6d8051e4aeef` |
| Client → hub packet | Write with response. Byte `0x06` (`WRITE_STDIN`), followed by UTF-8 command text ending in LF (`0x0A`). |
| Hub → client notification | First byte `0x01` means `WRITE_STDOUT`. Treat the remaining bytes as a continuous UTF-8 stream. |
| Framing | Buffer stdout until LF. A notification may contain part of a line, one full line, or multiple lines. Notification boundaries are not message boundaries. |
| Connection model | Disconnect any existing client before connecting another app; BLE supports one active host. |

```text
Command packet:  06 44 52 56 20 2D 33 35 20 2D 33 35 0A
                 |  D  R  V     -  3  5     -  3  5  LF

Notification:    01 52 45 41 44 59 0A  → stdout line: READY
```

## 4. Session lifecycle

1. Scan for devices advertising the Pybricks service UUID and let the user select a hub.
2. Connect, discover the command/event characteristic, and enable notifications.
3. Set the UI to **Connected — start the Pybricks program**. Do not enable motion controls yet.
4. On `READY`, set `ready = true` and enable approved controls. `STOP` may remain available after connection.
5. Send one LF-terminated command for each action. Await `ACK`, `ERR`, `SAFE`, or timeout before reporting completion.
6. On disconnect, clear ready state, buffered stdout, pending-command state, and motion UI state.

## 5. Command set (client → hub)

Commands are uppercase ASCII tokens separated by one space and terminated by LF. New apps must send only the allow-listed commands below.

| Command | Arguments | Meaning | Expected hub response |
| --- | --- | --- | --- |
| `STOP` | none | Immediately stops both drive motors. | `ACK STOP` |
| `PING` | none | Liveness check; no movement. | `ACK PING` |
| `ECHO <text>` | UTF-8 diagnostic text; total command length must remain within the hub’s 32-character input limit | Returns the supplied text unchanged. Use it to test LF framing, stdout reassembly, UTF-8 handling, and round-trip application logging; it never moves the robot. | `ECHO <text>` |
| `DRV <left> <right>` | signed integers, nominally `−55…55` | Sets left/right wheel power. Motor signs are defined by the hub configuration. | `ACK DRV <left> <right>`; an obstacle stop emits `SAFE obstacle` before the ACK. |
| `HEAD <degrees>` | integer, nominally `−60…60` | Tracks the head to a target angle. The hub clamps the target. | `ACK HEAD <clamped degrees>` |
| `COLORLIGHT <s1> <s2> <s3>` | three integers, each `0…100` | Sets the three Color Sensor light segments (Port A) independently. `0 0 0` turns that eye off. | `ACK COLORLIGHT <s1> <s2> <s3>` |
| `ULTRALIGHT <l1> <l2> <l3> <l4>` | four integers, each `0…100` | Sets the four Ultrasonic Sensor LEDs (Port B) independently. `0 0 0 0` turns that eye off. | `ACK ULTRALIGHT <l1> <l2> <l3> <l4>` |
| `LIGHTS OFF` | none | Turns off both sensor-light assemblies. | `ACK LIGHTS OFF` |

Recommended UI mappings:

| Action | Command |
| --- | --- |
| Forward | `DRV -35 -35` |
| Reverse | `DRV 35 35` |
| Left | `DRV -35 35` |
| Right | `DRV 35 -35` |
| Head left | `HEAD -45` |
| Head right | `HEAD 45` |
| Stop | `STOP` |

### Sensor-light behavior

`COLORLIGHT` controls the three physical light segments on the Color Sensor; values are **segment brightnesses**, not RGB colour channels. `ULTRALIGHT` controls the Ultrasonic Sensor’s four physical LEDs in order. Apps should use values from `0` to `100` inclusive.

Useful presets:

| Effect | Color Sensor (Port A) | Ultrasonic Sensor (Port B) |
| --- | --- | --- |
| All on | `COLORLIGHT 100 100 100` | `ULTRALIGHT 100 100 100 100` |
| Awake / balanced | `COLORLIGHT 30 30 30` | `ULTRALIGHT 30 30 30 30` |
| Happy outer eye pattern | `COLORLIGHT 30 30 30` | `ULTRALIGHT 100 0 0 100` |
| Sad inner eye pattern | `COLORLIGHT 30 30 30` | `ULTRALIGHT 0 100 100 0` |
| All off | `LIGHTS OFF` | `LIGHTS OFF` |

Lights are cosmetic and do not affect drive safety, obstacle detection, or the two-second drive timeout. A `STOP` command stops motors only; it leaves the selected light state unchanged. The hub program should return `ERR invalid-colorlight` or `ERR invalid-ultralight` when the segment count is wrong or a value is not an integer; it should clamp valid numeric values to `0…100` and acknowledge the applied values.

### Diagnostics

Use `PING` for a simple liveness check and `ECHO` for end-to-end protocol diagnostics. For example, send `ECHO test-123`; a healthy hub returns exactly `ECHO test-123` as one LF-terminated stdout line. A client should log the elapsed time from write initiation to the matching response, but it must not use a successful diagnostic response as proof that drive hardware is safe or available.

## 6. Events and responses (hub → client)

| Line | Meaning | Client action |
| --- | --- | --- |
| `READY` | Hub program has started and accepts commands. | Set `ready = true`; enable normal controls. |
| `ACK <command>` | Command was accepted and executed or scheduled. | Resolve the matching pending command and update the UI. |
| `ECHO <text>` | Echo response for a diagnostic request. | Match it with the pending `ECHO` command, record round-trip timing, and show/log a transport diagnostic result. |
| `ERR invalid-drive` / `ERR invalid-head` | Argument could not be parsed. | Show a non-motion error; keep the connection alive. |
| `ERR invalid-colorlight` / `ERR invalid-ultralight` | A sensor-light command has the wrong number of segments or a non-integer value. | Keep the connection alive; retain the previous light state. |
| `ERR line-too-long` | Input exceeded the hub line buffer. | Treat as a client bug; stop sending and log diagnostic context. |
| `ERR <command>` | Unsupported command. | Treat as an integration error; do not retry blindly. |
| `SAFE obstacle` / `SAFE shoulder` | Hub stopped drive because of an obstacle or touch switch. | Immediately show safety state; never auto-resume movement. |
| `TEL d=<mm> r=<0–100> touch=<0\|1> h=<degrees>` | Periodic sensor and motion telemetry (currently every 500 ms). | Parse known key/value fields and ignore unknown future fields. |

## 7. Safety and reliability requirements

- The hub has a mandatory two-second command timeout. For sustained movement, refresh `DRV` every 250–500 ms while control is held, then send `STOP` on release.
- A `SAFE` event, disconnect, app backgrounding, BLE write failure, or control timeout must make the client visibly stopped. Never replay the prior motion command automatically.
- Treat `ACK` as application-level confirmation. A successful BLE write confirms transport delivery, not motor execution.
- Use one in-flight motion command per client. Coalesce rapid joystick or button updates so stale queued input cannot restart movement after `STOP`.
- Do not depend on telemetry for safety: stdout is non-blocking, so the hub can drop telemetry or ACK lines when its small output buffer is full.

## 8. Platform implementation notes

| Platform | Required approach |
| --- | --- |
| iOS (CoreBluetooth) | Use the Pybricks UUIDs. Write `Data([0x06]) + utf8(command + "\n")` with response; subscribe to the same characteristic; strip the `0x01` event byte and line-buffer stdout. Replace the fixed-three-byte demo controller for Wall‑E mode. |
| Android (BluetoothGatt) | Scan by service UUID, connect GATT, discover services, enable characteristic notifications/CCCD, write the `0x06`-prefixed LF-terminated payload with response, and line-buffer data after `0x01`. |
| Python web bridge (Bleak) | Maintain one async BLE client for the Flask app. Restrict HTTP actions to an allow-list that maps to the command set; do not expose raw command text on public endpoints. |
| Raspberry Pi 4 native Python program (Bleak) | Run a direct `asyncio` + Bleak client without Flask, a browser, or HTTP. Scan/connect/subscribe once, line-buffer stdout after `0x01`, then call the same allow-listed `send()` method from a CLI, GPIO loop, camera/vision worker, or systemd service. |
| Hub program (Pybricks) | Poll stdin, build a bounded LF-delimited line, emit documented text lines with `print`, and retain authority for safety conditions and output cadence. |

## 9. Raspberry Pi 4 native Python client

A Raspberry Pi 4 can control the hub directly without starting the web application. This is suitable for a local command-line remote, a GPIO-button controller, an autonomous vision process, or a background `systemd` service.

### Runtime and operating requirements

- Use Python 3.10+ and [`bleak`](https://bleak.readthedocs.io/) with the system BlueZ Bluetooth stack.
- Install BlueZ on Raspberry Pi OS: `sudo apt install bluez`; run the program as a user with Bluetooth access (or configure the service with `SupplementaryGroups=bluetooth`).
- The Pi is the only active BLE host while it controls the hub. Stop the iOS, Android, or web client first.
- Keep a single `BleakClient` instance for the process. Only one coroutine may write a motion command at a time.
- On process shutdown, cancellation, GPIO release, vision-worker error, or lost connection, send `STOP` when still connected, then disconnect.

### Reference client

```python
import asyncio
from bleak import BleakClient, BleakScanner

SERVICE_UUID = "c5f50001-8280-46da-89f4-6d8051e4aeef"
COMMAND_UUID = "c5f50002-8280-46da-89f4-6d8051e4aeef"


class PybricksPiClient:
    def __init__(self):
        self.ready = asyncio.Event()
        self.stdout = bytearray()
        self.write_lock = asyncio.Lock()

    def on_notification(self, _sender, data: bytearray):
        if not data or data[0] != 0x01:  # Pybricks WRITE_STDOUT
            return
        self.stdout.extend(data[1:])
        while b"\n" in self.stdout:
            raw, _, remainder = self.stdout.partition(b"\n")
            self.stdout = bytearray(remainder)
            self.handle_line(raw.decode("utf-8", errors="replace").strip())

    def handle_line(self, line: str):
        print(f"← {line}")
        if line == "READY":
            self.ready.set()
        elif line.startswith("SAFE "):
            # Stop local autonomous control; never resume automatically.
            print(f"Safety stop: {line[5:]}")

    async def send(self, client: BleakClient, command: str):
        allowed = {"STOP", "PING", "ECHO", "DRV", "HEAD", "COLORLIGHT", "ULTRALIGHT", "LIGHTS"}
        if command.split(maxsplit=1)[0] not in allowed:
            raise ValueError("Unsupported hub command")
        async with self.write_lock:
            payload = b"\x06" + (command + "\n").encode("utf-8")
            await client.write_gatt_char(COMMAND_UUID, payload, response=True)
            print(f"→ {command}")


async def main():
    device = await BleakScanner.find_device_by_filter(
        lambda d, adv: SERVICE_UUID in {u.lower() for u in (adv.service_uuids or [])},
        timeout=10.0,
    )
    if device is None:
        raise RuntimeError("No Pybricks hub found")

    remote = PybricksPiClient()
    async with BleakClient(device) as client:
        await client.start_notify(COMMAND_UUID, remote.on_notification)
        # Start (or restart) the hub program now so its READY line is observed.
        await asyncio.wait_for(remote.ready.wait(), timeout=15.0)
        await remote.send(client, "ECHO pi4-diagnostic")
        await remote.send(client, "COLORLIGHT 30 30 30")
        await remote.send(client, "ULTRALIGHT 30 30 30 30")
        await remote.send(client, "DRV -35 -35")
        await asyncio.sleep(0.5)
        await remote.send(client, "STOP")


if __name__ == "__main__":
    asyncio.run(main())
```

For sustained motion, replace the one-shot `DRV` example with a task that sends the current drive values every 250–500 ms while the control is active. Always cancel that task and send `STOP` when the control is released.

## 10. Android reference pseudocode

```kotlin
fun onNotification(bytes: ByteArray) {
    if (bytes.isEmpty() || bytes[0] != 0x01.toByte()) return
    stdoutBuffer.append(bytes.copyOfRange(1, bytes.size))
    while (stdoutBuffer.contains(LF)) {
        val line = decodeUtf8(stdoutBuffer.popLine()).trim()
        handleHubLine(line)
    }
}

fun send(command: String) {
    require(connected && (ready || command == "STOP"))
    val payload = byteArrayOf(0x06) + (command + "\n").encodeToByteArray()
    commandEvent.write(payload, WRITE_TYPE_DEFAULT)
}
```

## 11. Compatibility and versioning

The repository contains two different protocols:

- The `PybricksRemote` iOS demo uses an unframed, fixed three-byte exchange: `rdy`, `fwd` / `rev` / `stp`, then `ack:`.
- The Wall‑E companion and Raspberry Pi web bridge use the newline-delimited protocol in this document. `walle_companion_excited_eyes.py`, the hub program used by the Pi web app, implements `ECHO`, `COLORLIGHT`, `ULTRALIGHT`, and `LIGHTS OFF`. Other hub programs in this repository may not; select the excited-eyes program before enabling those controls.

They are not interoperable without a translation layer. Both variants use the same Pybricks transport service, so clients must not infer protocol mode from UUIDs.

Future capabilities should add uppercase commands or events. Clients should ignore unknown `TEL` fields and display unknown event lines as diagnostics only.

## 12. Acceptance checklist

- [ ] Client discovers only advertised Pybricks-service hubs and handles Bluetooth permission/state errors.
- [ ] Client reconstructs `READY`, `ACK`, `SAFE`, `ERR`, and `TEL` across split or combined notifications.
- [ ] Client sends exactly `0x06 + UTF-8(command) + LF` and uses write-with-response.
- [ ] `STOP`, disconnect, backgrounding, write failure, and `SAFE` all leave the UI visibly stopped without auto-resume.
- [ ] Sustained drive refreshes occur before the hub’s two-second timeout; release sends `STOP`.
- [ ] `PING` returns `ACK PING`, and `ECHO test-123` returns exactly `ECHO test-123` across split or combined BLE notifications.
- [ ] Each sensor-light command validates its full segment list, applies the new pattern atomically, and acknowledges the applied values.
- [ ] A malformed light command leaves the current eye state unchanged and returns the documented `ERR` line.
- [ ] The Raspberry Pi native client runs without Flask or a browser, subscribes before waiting for `READY`, and sends `STOP` during orderly shutdown.
- [ ] No UI or HTTP endpoint permits arbitrary hub command injection; commands are allow-listed and logged safely.

## Appendix: workspace sources

- Hub behavior: `walle_hub/walle_companion.py`
- Web BLE bridge: `rpi_yolo_webapp/app.py`
- Existing iOS fixed-length demo: `ios/PybricksRemote/PybricksRemote/PybricksHubController.swift`

This specification records the currently implemented Wall‑E protocol; it is not an official Pybricks protocol reference.
