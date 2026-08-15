#!/usr/bin/env python3
"""Mobile-friendly YOLOv8 webcam stream for a headless Raspberry Pi.

The camera and model are intentionally owned by one background worker.  Every
browser receives the most recent annotated JPEG, so opening a second phone does
not open /dev/video0 again or double the inference load.
"""

from __future__ import annotations

import atexit
import logging
import os
import threading
import time
from dataclasses import dataclass

import cv2
from flask import Flask, Response, jsonify, render_template
from ultralytics import YOLO


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
LOG = logging.getLogger(__name__)


@dataclass
class StreamStatus:
    fps: float = 0.0
    inference_ms: float = 0.0
    error: str | None = None


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
    worker.start()
    atexit.register(worker.stop)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/video_feed")
    def video_feed():
        return Response(worker.frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.get("/health")
    def health():
        status = worker.status()
        return jsonify(status.__dict__), 503 if status.error else 200

    return app


app = create_app()

if __name__ == "__main__":
    # Use a production server such as waitress on the Pi; Flask is convenient
    # for directly testing the application.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), threaded=True)
