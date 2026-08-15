# Wall-E Vision (Raspberry Pi 4)

A headless, mobile-friendly web viewer for a USB webcam and YOLOv8n. It uses a
single camera/inference worker and shares its annotated MJPEG frames with every
browser connected to the Pi. This avoids the unreliable per-browser camera
capture pattern and is suitable for a phone-based replacement of the iOS camera
screen.

This app intentionally does **not** send LEGO drive commands. Keep the existing
Pybricks safety controls and stop the robot before handling it.

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

Open `http://<pi-ip-address>:5000` from a phone on the same network. The
`/health` endpoint returns frame inference timing and reports camera/model
errors as HTTP 503.

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
