# Wall-E Companion

This is a separate iPhone remote for the existing wheeled Wall-E-style SPIKE Prime build. It does not require any physical redesign.

## Wiring

| Port | Existing component | App function |
| --- | --- | --- |
| A | Color Sensor | Reflection telemetry (second eye) |
| B | Ultrasonic Sensor | Obstacle safety and distance telemetry (first eye) |
| C | Motor | Head left/right |
| D | Motor | Left wheel |
| E | Force Sensor | Shoulder emergency stop |
| F | Motor | Right wheel |

## Run the hub

1. Put the robot on a stand so its wheels can turn freely.
2. Point the head straight ahead, then start [`walle_companion_excited_eyes.py`](../../walle_hub/walle_companion_excited_eyes.py) from the Pybricks app.
3. If either wheel goes the wrong way, stop the program and change only its matching `LEFT_SIGN` or `RIGHT_SIGN` value from `1` to `-1`.

The program publishes `READY` when Bluetooth control is available. It rejects forward motion when the ultrasonic eye is closer than 180 mm, stops immediately on a shoulder touch, and stops if it receives no command for two seconds.

## Build and use the iPhone app

1. Open [`WallECompanion.xcodeproj`](WallECompanion.xcodeproj) in Xcode.
2. Select the **WallECompanion** target, choose your Apple Development Team under **Signing & Capabilities**, and use a unique bundle identifier if Xcode asks.
3. Select the connected iPhone and press Run. On first launch allow Bluetooth, Camera, Microphone, and Speech Recognition access.
4. Start the hub program, then choose the discovered Pybricks Hub in the app.
5. Wait for **Robot ready**, then use Forward, Reverse, Stop, Head L, or Head R.
6. To play music, press Wall-E's shoulder button to disable the wheels. Once the app shows **Wheels disabled — stopped**, tap **Play WALL-E music**. It opens the configured [YouTube Music radio](https://www.youtube.com/watch?v=OLMffDM7hSI&list=RDOLMffDM7hSI&start_radio=1) (or the browser if the YouTube Music app is not installed).

The front-camera tile is optional. With **Face control** enabled, moving your face left sends Forward; moving it right sends Reverse. Voice commands recognise “forward”, “back/reverse”, “stop”, “look left”, and “look right”.

## Bluetooth protocol

The app and hub exchange newline-delimited UTF-8 messages over Pybricks stdin/stdout:

```
DRV 40 40
HEAD -45
STOP
```

The hub returns `ACK …`, `SAFE …`, `WHEELS …`, and `TEL …` messages. The bottom command log displays all of them. The app enables the music link only after it receives `WHEELS OFF` (or equivalent telemetry), which means the shoulder toggle has stopped and disabled the drive.
