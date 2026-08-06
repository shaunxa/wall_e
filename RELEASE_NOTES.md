# Wall-E Companion — Release Notes

## v0.1.0 — 5 August 2026

First working feasibility release for the LEGO SPIKE Prime Wall-E-style robot and iPhone companion.

### iPhone app

- Pybricks BLE connection, discovery, command acknowledgements, telemetry, and command log.
- Manual left, right, stop, and head-pan controls.
- Correct Pybricks stdin packet framing for reliable motor commands.
- Front-camera face tracking:
  - turns left/right to centre a detected face;
  - moves forward when the face is below the configured distance range;
  - reverses when the face is above the configured distance range.
- Configurable face-width distance band, defaulting to 20–40% of the camera view.
- Optional voice commands.
- Camera, microphone, speech-recognition, Bluetooth, portrait, and landscape support.
- Red **Wheels disabled — stopped** indicator below the camera view when the shoulder touch toggle disables the drive.
- A **Play WALL-E music** link that is available only while the wheel toggle has stopped the robot; it opens the configured YouTube Music radio.

### SPIKE Prime hub

- Port mapping:

  | Port | Component |
  | --- | --- |
  | A | Color Sensor eye |
  | B | Ultrasonic Sensor eye / obstacle detector |
  | C | Head motor |
  | D | Left wheel motor |
  | E | Force Sensor shoulder toggle |
  | F | Right wheel motor |

- Wheel-direction calibration for the mirrored D/F motor layout.
- 20T-to-56T head-gear calibration, including direction reversal and physical head-angle telemetry.
- Obstacle stop using the Ultrasonic Sensor.
- Two-second command timeout stop.
- Shoulder touch toggles wheel drive on/off; disabling immediately stops the wheels.
- `READY`, `ACK`, `SAFE`, `WHEELS`, and `TEL` messages sent to the app.

### Personality programs

- [walle_companion_touch_toggle.py](walle_hub/walle_companion_touch_toggle.py): touch-toggle wheel control.
- [walle_companion_idle_eyes.py](walle_hub/walle_companion_idle_eyes.py): idle blink and slow head sweep after five seconds stopped.
- [walle_companion_excited_eyes.py](walle_hub/walle_companion_excited_eyes.py): moving eye animation—Ultrasonic Sensor lights fully on while Color Sensor segments chase every second.

### Known limitation

The Color Sensor supports individual brightness control of its three light segments, but not programmable red/green/blue colours. The moving expression is therefore a three-segment brightness chase, not a true RGB animation.
