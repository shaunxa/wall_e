#!/usr/bin/env python3
"""Mobile-friendly YOLOv8 webcam stream for a headless Raspberry Pi.

The camera and model are intentionally owned by one background worker.  Every
browser receives the most recent annotated JPEG, so opening a second phone does
not open /dev/video0 again or double the inference load.
"""

from __future__ import annotations

import atexit
import asyncio
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

import cv2
from bleak import BleakClient, BleakScanner
from flask import Flask, Response, jsonify, render_template, request
from ultralytics import YOLO


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
LOG = logging.getLogger(__name__)

# Pybricks command/event GATT service used by the existing Wall-E hub program.
PYBRICKS_SERVICE_UUID = "c5f50001-8280-46da-89f4-6d8051e4aeef"
PYBRICKS_COMMAND_UUID = "c5f50002-8280-46da-89f4-6d8051e4aeef"


@dataclass
class StreamStatus:
    fps: float = 0.0
    inference_ms: float = 0.0
    error: str | None = None


class PybricksBridge:
    """Own one asynchronous Bleak connection for the Flask application."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="pybricks-ble", daemon=True)
        self._thread.start()
        self._client: BleakClient | None = None
        self._lock = threading.Lock()
        self._command_lock = threading.Lock()
        self._stdout = bytearray()
        self._state: dict[str, Any] = {
            "connected": False, "ready": False, "name": None, "address": None,
            "status": "Not connected", "telemetry": "Distance — · Reflection — · Touch —",
            "wheels_enabled": True, "log": [],
        }

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _call(self, coroutine: Any, timeout: float = 20) -> Any:
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result(timeout=timeout)

    def _update(self, **values: Any) -> None:
        with self._lock:
            self._state.update(values)

    def _append_log(self, text: str) -> None:
        with self._lock:
            self._state["log"] = [*self._state["log"], text][-80:]

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {**self._state, "log": list(self._state["log"])}

    def scan(self) -> list[dict[str, str | int | None]]:
        return self._call(self._scan())

    async def _scan(self) -> list[dict[str, str | int | None]]:
        devices = await BleakScanner.discover(timeout=5.0, return_adv=True)
        hubs: list[dict[str, str | int | None]] = []
        for device, advertisement in devices.values():
            service_uuids = {uuid.lower() for uuid in (advertisement.service_uuids or [])}
            if PYBRICKS_SERVICE_UUID not in service_uuids:
                continue
            hubs.append({"name": device.name or advertisement.local_name, "address": device.address,
                         "rssi": getattr(advertisement, "rssi", None)})
        return sorted(hubs, key=lambda hub: (hub["name"] or "", hub["address"] or ""))

    def connect(self, address: str) -> dict[str, Any]:
        self._call(self._connect(address))
        return self.status()

    async def _connect(self, address: str) -> None:
        await self._disconnect()
        self._update(status="Connecting…")
        client = BleakClient(address, disconnected_callback=self._on_disconnect)
        await client.connect(timeout=15.0)
        try:
            characteristics = {char.uuid.lower() for service in client.services for char in service.characteristics}
            if PYBRICKS_COMMAND_UUID not in characteristics:
                raise ValueError("The device does not expose the Pybricks command characteristic")
            await client.start_notify(PYBRICKS_COMMAND_UUID, self._on_notification)
        except Exception:
            await client.disconnect()
            raise
        self._client = client
        self._stdout.clear()
        self._update(connected=True, ready=False, name=getattr(client, "name", None), address=address,
                     status="Connected — start the Pybricks program", telemetry="Distance — · Reflection — · Touch —",
                     wheels_enabled=True, log=[])

    def disconnect(self) -> dict[str, Any]:
        self._call(self._disconnect())
        return self.status()

    async def _disconnect(self) -> None:
        client, self._client = self._client, None
        if client and client.is_connected:
            try:
                await client.stop_notify(PYBRICKS_COMMAND_UUID)
            except Exception:
                pass
            await client.disconnect()
        self._update(connected=False, ready=False, name=None, address=None, status="Not connected", wheels_enabled=True)

    def command(self, action: str) -> dict[str, Any]:
        commands = {"stop": ("STOP",), "left": ("DRV 35 -35",), "right": ("DRV -35 35",),
                    "forward": ("DRV -35 -35",), "reverse": ("DRV 35 35",),
                    "ping": ("PING",), "echo": ("ECHO web-diagnostic",),
                    "eyes_awake": ("COLORLIGHT 30 30 30", "ULTRALIGHT 30 30 30 30"),
                    "eyes_off": ("LIGHTS OFF",)}
        if action not in commands:
            raise ValueError("Unsupported action")
        if action != "stop" and not self.status()["ready"]:
            raise RuntimeError("Hub program is not ready")
        with self._command_lock:
            for command in commands[action]:
                self._call(self._send(command))
        return self.status()

    def head(self, angle: int) -> dict[str, Any]:
        if isinstance(angle, bool) or not isinstance(angle, int) or not -45 <= angle <= 45:
            raise ValueError("Head angle must be an integer from -45 to 45")
        if not self.status()["ready"]:
            raise RuntimeError("Hub program is not ready")
        with self._command_lock:
            self._call(self._send(f"HEAD {angle}"))
        return self.status()

    async def _send(self, command: str) -> None:
        if not self._client or not self._client.is_connected:
            raise RuntimeError("Hub is not connected")
        # 0x06 directs following bytes to the running Pybricks program's stdin.
        await self._client.write_gatt_char(PYBRICKS_COMMAND_UUID, b"\x06" + (command + "\n").encode(), response=True)
        self._append_log(f"→ {command}")

    def _on_notification(self, _sender: Any, data: bytearray) -> None:
        if data and data[0] == 0x01:
            self._stdout.extend(data[1:])
            while b"\n" in self._stdout:
                raw_line, _, remainder = self._stdout.partition(b"\n")
                self._stdout = bytearray(remainder)
                self._handle_line(raw_line.decode("utf-8", errors="replace").strip())

    def _handle_line(self, line: str) -> None:
        if not line:
            return
        self._append_log(f"← {line}")
        if line == "READY":
            self._update(ready=True, status="Connected — robot ready")
        elif line.startswith("SAFE "):
            self._update(status=f"Safety stop: {line[5:]}")
        elif line == "WHEELS OFF":
            self._update(wheels_enabled=False)
        elif line == "WHEELS ON":
            self._update(wheels_enabled=True)
        elif line.startswith("TEL "):
            enabled = self.status()["wheels_enabled"]
            if "wheels=" in line:
                enabled = "wheels=0" not in line
            self._update(telemetry=line[4:].replace(" ", " · "), wheels_enabled=enabled)

    def _on_disconnect(self, _client: BleakClient) -> None:
        self._client = None
        self._update(connected=False, ready=False, name=None, address=None, status="Disconnected", wheels_enabled=True)

    def stop(self) -> None:
        try:
            self.disconnect()
        except Exception:
            LOG.exception("Could not close Pybricks BLE connection")
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=3)


class CameraWorker:
    """Capture, infer, and publish the latest JPEG frame from one thread."""

    def __init__(self, camera_index: int, width: int, height: int, model_path: str) -> None:
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.model_path = model_path
        self._condition = threading.Condition()
        self._frame: bytes | None = None
        self._sequence = 0
        self._status = StreamStatus()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._capture: cv2.VideoCapture | None = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="yolo-camera", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._condition:
            self._condition.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=3)
        if self._capture is not None:
            self._capture.release()

    def status(self) -> StreamStatus:
        with self._condition:
            return StreamStatus(**self._status.__dict__)

    def frames(self):
        """Yield a frame only after it changes, keeping slow clients cheap."""
        last_sequence = -1
        while not self._stop.is_set():
            with self._condition:
                self._condition.wait_for(
                    lambda: self._sequence != last_sequence or self._stop.is_set(), timeout=5
                )
                if self._stop.is_set():
                    return
                frame = self._frame
                last_sequence = self._sequence
            if frame is not None:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"

    def _set_error(self, message: str) -> None:
        LOG.warning(message)
        with self._condition:
            self._status.error = message
            self._condition.notify_all()

    def _run(self) -> None:
        try:
            LOG.info("Loading YOLO model: %s", self.model_path)
            model = YOLO(self.model_path)
            self._capture = cv2.VideoCapture(self.camera_index)
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            if not self._capture.isOpened():
                self._set_error(f"Cannot open camera index {self.camera_index}")
                return

            while not self._stop.is_set():
                ok, frame = self._capture.read()
                if not ok:
                    self._set_error("Could not read a frame from the camera")
                    time.sleep(0.2)
                    continue

                results = model(frame, imgsz=320, verbose=False)
                annotated = results[0].plot()
                inference_ms = float(results[0].speed.get("inference", 0.0))
                fps = 1000 / inference_ms if inference_ms > 0 else 0.0
                cv2.putText(
                    annotated, f"YOLOv8n  {fps:.1f} FPS", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 2,
                )
                encoded, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if not encoded:
                    self._set_error("Could not encode camera frame as JPEG")
                    continue
                with self._condition:
                    self._frame = jpeg.tobytes()
                    self._sequence += 1
                    self._status = StreamStatus(fps=fps, inference_ms=inference_ms)
                    self._condition.notify_all()
        except Exception as exc:  # Keep the status endpoint useful on headless deployments.
            self._set_error(f"Camera worker stopped: {exc}")
            LOG.exception("Camera worker stopped")


def create_app() -> Flask:
    app = Flask(__name__)
    worker = CameraWorker(
        camera_index=int(os.getenv("CAMERA_INDEX", "0")),
        width=int(os.getenv("CAMERA_WIDTH", "640")),
        height=int(os.getenv("CAMERA_HEIGHT", "480")),
        model_path=os.getenv("YOLO_MODEL", "yolov8n.pt"),
    )
    bridge = PybricksBridge()
    worker.start()
    atexit.register(worker.stop)
    atexit.register(bridge.stop)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/video_feed")
    def video_feed():
        return Response(worker.frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.get("/health")
    def health():
        status = worker.status()
        return jsonify(camera=status.__dict__, hub=bridge.status()), 503 if status.error else 200

    @app.get("/api/hub/scan")
    def scan_hubs():
        try:
            return jsonify(hubs=bridge.scan())
        except Exception as exc:
            LOG.exception("Pybricks BLE scan failed")
            return jsonify(error=str(exc)), 503

    @app.post("/api/hub/connect")
    def connect_hub():
        address = (request.get_json(silent=True) or {}).get("address")
        if not isinstance(address, str) or not address:
            return jsonify(error="A hub BLE address is required"), 400
        try:
            return jsonify(hub=bridge.connect(address))
        except Exception as exc:
            LOG.exception("Pybricks BLE connection failed")
            return jsonify(error=str(exc)), 503

    @app.post("/api/hub/disconnect")
    def disconnect_hub():
        try:
            return jsonify(hub=bridge.disconnect())
        except Exception as exc:
            return jsonify(error=str(exc)), 503

    @app.post("/api/hub/command")
    def hub_command():
        action = (request.get_json(silent=True) or {}).get("action")
        if not isinstance(action, str):
            return jsonify(error="An action is required"), 400
        try:
            return jsonify(hub=bridge.command(action))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except Exception as exc:
            LOG.warning("Hub command failed: %s", exc)
            return jsonify(error=str(exc)), 503

    @app.post("/api/hub/head")
    def hub_head():
        angle = (request.get_json(silent=True) or {}).get("angle")
        try:
            return jsonify(hub=bridge.head(angle))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except Exception as exc:
            LOG.warning("Head command failed: %s", exc)
            return jsonify(error=str(exc)), 503

    return app


app = create_app()

if __name__ == "__main__":
    # Use a production server such as waitress on the Pi; Flask is convenient
    # for directly testing the application.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), threaded=True)
