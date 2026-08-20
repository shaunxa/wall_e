# Wall-E Vision (Raspberry Pi 4)

A headless, mobile-friendly web viewer for a USB webcam and YOLOv8n. It uses a
single camera/inference worker and shares its annotated MJPEG frames with every
browser connected to the Pi. This avoids the unreliable per-browser camera
capture pattern and is suitable for a phone-based replacement of the iOS camera
screen.

It also connects directly to the existing Wall-E Pybricks program over BLE and
provides a browser control deck: live video, hold-to-drive joystick, −45° to
45° head control, hub status/telemetry, diagnostics, and sensor-eye lights.
The hub retains the safety logic: obstacle rejection, shoulder wheel-disable
switch, and the two-second command timeout. Keep the robot in a clear area and
use **Stop** before handling it.

## Install on the Pi

From the directory containing this folder (for example `~/hello_ev3`):

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r rpi_yolo_webapp/requirements.txt
cd rpi_yolo_webapp
../.venv/bin/python app.py
```

On first start, Ultralytics downloads `yolov8n.pt` if it is not already in the
current directory. For an offline Pi, copy that file beside `app.py` first.

## Use Wall-E Vision without an external Wi-Fi network

This Pi is configured with [RaspberryConnect AccessPopup](https://github.com/RaspberryConnect/AccessPopup).
When no known Wi-Fi network is available, it creates its own Wi-Fi access point
so the phone can connect directly to Wall-E Vision.

1. Power on the Pi and wait for the AccessPopup network to appear. If the Pi is
   currently connected to a known network, force standalone mode with
   `sudo accesspopup -a`.
2. On the phone, join the configured AccessPopup SSID. A phone may warn that it
   has no internet connection; stay connected because the Pi is providing a
   local-only network.
3. Open `http://192.168.50.5:5000` in the phone browser, unless the
   AccessPopup IP was changed during its setup. Use the configured AccessPopup
   IP in that case.
4. Scan for and connect to the Pybricks Hub from the page.

The AccessPopup defaults are SSID `AccessPopup`, password `1234567890`, and Pi
IP `192.168.50.5`; change the default password with AccessPopup's configuration
tool. In normal automatic mode, AccessPopup checks every two minutes for known
Wi-Fi networks and can switch between the AP and one of those networks. A
network switch disconnects the browser briefly, so use `sudo accesspopup -a`
when you need a stable standalone connection.

If connected through another Wi-Fi network instead, open
`http://<pi-ip-address>:5000`. The `/health` endpoint returns frame inference
timing and reports camera/model errors as HTTP 503.

## Connect the Pybricks Hub

1. Stop the iPhone app or any other program that is connected to the hub; BLE
   permits one active host connection.
2. Start `walle_companion_excited_eyes.py` on the hub.
3. In the web app, select **Scan hubs**, choose the Pybricks Hub, and press
   **Connect**.
4. Wait for **Connected — robot ready**. Hold a direction to drive; releasing
   it sends **Stop**. The arrow keys work as an alternative remote and
   <kbd>Space</kbd> stops.
5. Use the head slider for a bounded −45° to 45° target. **Ping hub** and
   **Echo test** are safe BLE diagnostics. **Eyes awake** and **Eyes off**
   control the Color Sensor and Ultrasonic Sensor light assemblies.

The app sends newline-delimited `DRV`, `HEAD`, `STOP`, `PING`, `ECHO`,
`COLORLIGHT`, `ULTRALIGHT`, and `LIGHTS OFF` commands. The commands are
deliberately restricted to the controls shown in the web UI; arbitrary hub
input is not exposed as an HTTP endpoint.

On Debian, BLE access requires BlueZ and a user allowed to use Bluetooth:

```bash
sudo apt install -y bluez
sudo usermod -aG bluetooth shaun
```

Log out and back in after changing group membership. The supplied systemd unit
sets `SupplementaryGroups=bluetooth video`; replace `shaun` with your Pi user
name in both the unit and the command above if needed.

## Camera settings

The defaults are camera index `0`, 640×480 capture, and `yolov8n.pt`. Override
them without editing code:

```bash
CAMERA_INDEX=0 CAMERA_WIDTH=640 CAMERA_HEIGHT=480 YOLO_MODEL=yolov8n.pt ../.venv/bin/python app.py
```

If OpenCV cannot access the webcam, verify the device with
`v4l2-ctl --list-devices`, confirm that no other program owns it, and add the
service user to the `video` group if necessary.

## Start automatically (systemd)

Edit the paths and `User=` in `walle-vision.service` if your Pi username or
installation directory differs, then install and start it:

```bash
sudo cp walle-vision.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now walle-vision
sudo systemctl status walle-vision
```

Use `journalctl -u walle-vision -f` to inspect startup or webcam errors.
