# Wall‑E Companion

The Wall‑E companion is a Pybricks program and shared Bluetooth control contract for the wheeled LEGO SPIKE Prime Wall‑E build. It is used by the iPhone remote and the Raspberry Pi 4 web control deck.

The active hub program is [`walle_companion_excited_eyes.py`](walle_hub/walle_companion_excited_eyes.py). Upload and start that program from the Pybricks app before connecting a remote.

## Hardware map

| Port | Component | Companion responsibility |
| --- | --- | --- |
| A | Color Sensor | Reflection telemetry and three-segment eye light |
| B | Ultrasonic Sensor | Distance telemetry, forward-obstacle safety, and four-LED eye light |
| C | Motor | Head movement |
| D | Motor | Left wheel |
| E | Force Sensor | Shoulder wheel-enable toggle / emergency stop |
| F | Motor | Right wheel |

## Start safely

1. Place Wall‑E on a stand for the first motor test.
2. Point the head forward, then run `walle_companion_excited_eyes.py` from the Pybricks app.
3. Wait for `READY` before enabling normal controls in the client.
4. Use only one host at a time: disconnect the iPhone, web browser/Pi bridge, or any other BLE client before connecting another.
5. Test forward, reverse, left, right, head, and Stop in an open area before operating on the floor.

The hub owns the physical safety behavior:

- Forward drive is rejected when the ultrasonic sensor detects an obstacle closer than 180 mm.
- Pressing the shoulder Force Sensor stops the wheels and toggles the wheel-enable state.
- Drive motors stop after two seconds without a drive command refresh.
- `STOP` always stops the wheels; it does not turn off the eye lights.

## Raspberry Pi 4 web control deck

The Pi application provides live YOLO video, a hold-to-drive joystick, head-angle slider, telemetry, diagnostics, and eye controls. See [`rpi_yolo_webapp/README.md`](rpi_yolo_webapp/README.md) for installation and systemd setup.

In the browser, hold a direction to drive and release it to send `STOP`. The current assembled chassis uses these observed steering mappings:

| Web control | Hub command |
| --- | --- |
| Left | `DRV -35 35` |
| Right | `DRV 35 -35` |
| Forward | `DRV -35 -35` |
| Reverse | `DRV 35 35` |

If your chassis has been assembled differently, change only `LEFT_SIGN` or `RIGHT_SIGN` in the hub program and repeat the stand test.

## iPhone remote

1. Open [`WallECompanion.xcodeproj`](ios/WallECompanion/WallECompanion.xcodeproj) in Xcode.
2. Choose an Apple Development Team under **Signing & Capabilities** and use a unique bundle identifier if required.
3. Run the app on a physical iPhone; grant Bluetooth, Camera, Microphone, and Speech Recognition permissions when requested.
4. Start the hub program, select the discovered Pybricks Hub, and wait for **Robot ready**.

The iPhone app supports manual drive and head control plus optional face-motion and voice control. The camera and music functions are iPhone-specific; the hub protocol itself is shared with the Pi web app.

To play music safely, press Wall‑E’s shoulder button to disable the wheels. Once the app shows **Wheels disabled — stopped**, tap **Play WALL‑E music**. It opens the configured [YouTube Music radio](https://www.youtube.com/watch?v=OLMffDM7hSI&list=RDOLMffDM7hSI&start_radio=1).

## BLE protocol

Clients use the Pybricks GATT service and command/event characteristic:

| Item | UUID / format |
| --- | --- |
| Service UUID | `c5f50001-8280-46da-89f4-6d8051e4aeef` |
| Command/event UUID | `c5f50002-8280-46da-89f4-6d8051e4aeef` |
| Client → hub | `0x06` followed by UTF-8 command text and LF (`\n`) |
| Hub → client | `0x01` followed by newline-delimited Pybricks stdout text |

BLE notifications are a byte stream: one line may be split across notifications, or several lines may arrive together. Clients must buffer stdout until LF.

### Commands

| Command | Purpose | Response |
| --- | --- | --- |
| `STOP` | Stop both drive motors. | `ACK STOP` |
| `PING` | Liveness check. | `ACK PING` |
| `ECHO <text>` | End-to-end framing and diagnostic check. | `ECHO <text>` |
| `DRV <left> <right>` | Set drive power; values are clamped to ±55. | `ACK DRV …` |
| `HEAD <degrees>` | Set head target; values are clamped to −60…60. | `ACK HEAD …` |
| `COLORLIGHT <s1> <s2> <s3>` | Set Color Sensor light-segment brightnesses, each 0…100. | `ACK COLORLIGHT …` |
| `ULTRALIGHT <l1> <l2> <l3> <l4>` | Set Ultrasonic Sensor LED brightnesses, each 0…100. | `ACK ULTRALIGHT …` |
| `LIGHTS OFF` | Turn off both eye-light assemblies. | `ACK LIGHTS OFF` |

Light commands override the hub’s idle/excited eye animation until the hub program is restarted. The program refreshes manual light patterns so Color Sensor reflection reads do not leave the eye in an unintended state.

### Hub events

| Event | Meaning |
| --- | --- |
| `READY` | Hub program is running and ready for commands. |
| `ACK …` | Command accepted. |
| `SAFE obstacle`, `SAFE shoulder`, `SAFE wheels-disabled` | Hub stopped or rejected drive for safety. Never auto-resume. |
| `WHEELS ON` / `WHEELS OFF` | Shoulder switch changed the drive enable state. |
| `TEL d=… r=… touch=… h=… wheels=…` | Distance, reflection, touch, head angle, and wheel status telemetry. |
| `ERR …` | Malformed or unsupported command. |

For the complete platform-neutral contract and acceptance checklist, read the [Pybricks Hub Integration Protocol](docs/pybricks-hub-integration-protocol.md).
