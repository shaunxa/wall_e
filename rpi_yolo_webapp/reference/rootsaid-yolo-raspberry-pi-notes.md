# Raspberry Pi YOLO: implementation notes

> Original reference: [Real-Time Object Detection – Run YOLO on Raspberry Pi](https://rootsaid.com/embedded-systems/yolo-raspberry-pi-object-detection/), RootSaid Community, accessed 2026-08-15.
>
> This is an original technical summary for this project, not a copy of the
> article. Consult the linked source for its complete walkthrough and updates.

## Relevance to Wall-E Vision

The source demonstrates CPU-only YOLOv8 Nano inference on a Raspberry Pi 4
using a Raspberry Pi Camera Module V1 and Picamera2. It supports the decisions
in this project to use the small `yolov8n.pt` model, capture at 640×480, and
infer at `imgsz=320`. The latter is the important performance setting: reducing
the model's input size has a major effect on Pi 4 throughput.

Our application differs in one useful respect: it sends annotated frames to a
browser as MJPEG rather than using `cv2.imshow`, which makes it suitable for a
headless Pi and phone viewing. It currently targets a V4L/OpenCV webcam
(`cv2.VideoCapture`). For the CSI camera, replace that capture source with a
Picamera2 adapter.

## Hardware and OS checklist

- Raspberry Pi 4 with a stable 5 V / 3 A USB-C supply.
- 64-bit Raspberry Pi OS or compatible Debian image; 64-bit is important for
  current Python ML packages.
- Either a USB webcam (the current app) or an OV5647 CSI camera (the source
  article's setup).
- A sufficiently large, reliable microSD card. PyTorch downloads and temporary
  installation files are large.

For a CSI camera, confirm the camera is working before debugging Python:

```bash
rpicam-hello --timeout 5000
```

This isolates cable, camera, and operating-system configuration problems from
the YOLO application. On Pi 4, the blue side of the CSI ribbon cable faces the
USB ports.

## Environment preparation

The source recommends installing the camera library and numerical dependencies
with apt, then isolating Python packages in a virtual environment. A virtual
environment prevents Debian's externally-managed-Python protection from being
overridden. If the virtual environment needs access to an apt-installed
`picamera2`, create it with system site packages enabled:

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv libopenblas-dev git python3-picamera2
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
```

For a USB webcam, `python3-picamera2` is not required. This project's
`requirements.txt` installs Ultralytics, OpenCV headless, Flask, and Waitress.

Large Python wheels may exhaust a small RAM-backed `/tmp`. Point pip's temporary
files at storage on the SD card when that happens:

```bash
mkdir -p "$HOME/pip-tmp"
TMPDIR="$HOME/pip-tmp" pip install --upgrade pip
TMPDIR="$HOME/pip-tmp" pip install -r rpi_yolo_webapp/requirements.txt
```

## Model and CPU compatibility

`yolov8n.pt` is the smallest standard YOLOv8 model and is the sensible starting
point for Pi 4 CPU inference. It is downloaded on first use; retain a local copy
for offline startup. Validate the model on a still image before adding live
camera capture.

Some Pi 4 installations have encountered a PyTorch `Illegal instruction` crash
with newer builds. The source reports success with `torch==2.6.0` and
`torchvision==0.21.0`, alongside this OpenBLAS setting:

```bash
export OPENBLAS_CORETYPE=ARMV8
```

Treat those versions as a troubleshooting fallback rather than blindly pinning
them: Python 3.13 availability and ARM wheels can differ from the source's test
environment. Record `python --version`, `pip freeze`, and the full error before
changing package versions. Add the environment variable to the systemd unit if
it proves necessary for this app.

## CSI-camera capture adaptation

The source uses Picamera2's preview configuration with RGB frames. The inference
and JPEG streaming steps remain the same; only the capture source changes.

```python
from picamera2 import Picamera2

camera = Picamera2()
camera.configure(camera.create_preview_configuration(
    main={"size": (640, 480), "format": "RGB888"}
))
camera.start()
time.sleep(2)  # allow automatic exposure to settle

# In the worker loop:
frame = camera.capture_array()
```

The existing `CameraWorker` would need a small capture abstraction so that its
`read()` call can use `capture_array()` for CSI hardware, and shutdown should
call `camera.stop()`.

## Performance and operational guidance

- Start with 640×480 capture and `imgsz=320`; measure inference time and FPS in
  the page's status display rather than assuming a fixed performance number.
- Use a smaller image size before trying a larger model. It is normally the
  highest-value tuning knob on a Pi 4.
- Run headless: this project uses browser MJPEG output, so it does not need a
  desktop, HDMI monitor, or `cv2.imshow`.
- Test the camera separately, then validate a single still-image inference,
  then start continuous detection. This shortens diagnosis considerably.
- For unreliable starts, inspect `journalctl -u walle-vision -f` and the app's
  `/health` endpoint.
- The default COCO model recognises common everyday object classes. It does not
  know LEGO-specific categories unless trained or replaced with a custom model.

## Source-derived next step

Once detection is stable, application-specific code can react to selected
classes. For this project, retain the SPIKE hub's independent safety checks and
avoid coupling object detection directly to wheel movement without an explicit
safety design, confidence thresholds, and a manual stop path.
