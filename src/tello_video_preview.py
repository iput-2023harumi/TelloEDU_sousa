"""Tello EDUの映像を表示するプレビュー画面"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from typing import Optional

import robomaster
from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from robomaster import robot


class VideoWorker(QThread):
    """接続と映像取得をGUIスレッドから分離して実行する"""

    status_changed = Signal(str)
    frame_ready = Signal(QImage)

    def __init__(self, local_ip: Optional[str] = None) -> None:
        super().__init__()
        self.local_ip = local_ip
        self._start_stream = threading.Event()
        self._stop_stream = threading.Event()
        self._shutdown = threading.Event()

    def start_stream(self) -> None:
        self._start_stream.set()
        self._stop_stream.clear()

    def stop_stream(self) -> None:
        self._stop_stream.set()
        self._start_stream.clear()

    def shutdown(self) -> None:
        self._shutdown.set()
        self._stop_stream.set()
        self._start_stream.clear()

    def run(self) -> None:
        drone = None
        camera = None
        streaming = False
        try:
            if self.local_ip:
                robomaster.config.LOCAL_IP_STR = self.local_ip

            self.status_changed.emit("Connecting...")
            drone = robot.Drone()
            drone.initialize()
            camera = drone.camera
            self.status_changed.emit("Connected")

            while not self._shutdown.is_set():
                if self._start_stream.is_set() and not streaming:
                    self.status_changed.emit("Starting video...")
                    camera.start_video_stream(display=False)
                    streaming = True
                    self._start_stream.clear()
                    self.status_changed.emit("Video streaming")

                if self._stop_stream.is_set() and streaming:
                    camera.stop_video_stream()
                    streaming = False
                    self._stop_stream.clear()
                    self.status_changed.emit("Connected")

                if streaming:
                    frame = camera.read_cv2_image()
                    if frame is None:
                        time.sleep(0.01)
                        continue
                    height, width, channels = frame.shape
                    image = QImage(
                        frame.data,
                        width,
                        height,
                        channels * width,
                        QImage.Format.Format_BGR888,
                    ).copy()
                    self.frame_ready.emit(image)
                else:
                    self._shutdown.wait(0.05)
        except Exception as exc:
            self.status_changed.emit(f"Error: {exc}")
        finally:
            if camera is not None and streaming:
                try:
                    camera.stop_video_stream()
                except Exception:
                    pass
            if drone is not None:
                try:
                    drone.close()
                except Exception:
                    pass
            self.status_changed.emit("Disconnected")


class VideoPreviewWindow(QMainWindow):
    def __init__(self, local_ip: Optional[str] = None) -> None:
        super().__init__()
        self.setWindowTitle("Tello EDU Video Preview")
        self.resize(900, 620)

        self.video_label = QLabel("Connect to Tello EDU to begin")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(640, 360)
        self.video_label.setStyleSheet("background-color: #171717; color: #eeeeee;")

        self.status_label = QLabel("Disconnected")
        self.connect_button = QPushButton("Connect")
        self.start_button = QPushButton("Start video")
        self.stop_button = QPushButton("Stop video")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)

        button_row = QHBoxLayout()
        button_row.addWidget(self.connect_button)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)

        layout = QVBoxLayout()
        layout.addWidget(self.video_label, stretch=1)
        layout.addWidget(self.status_label)
        layout.addLayout(button_row)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.worker = VideoWorker(local_ip)
        self.worker.status_changed.connect(self._on_status_changed)
        self.worker.frame_ready.connect(self._on_frame_ready)
        self.worker.finished.connect(self._on_worker_finished)
        self.connect_button.clicked.connect(self._connect)
        self.start_button.clicked.connect(self._start_video)
        self.stop_button.clicked.connect(self._stop_video)

    def _connect(self) -> None:
        self.connect_button.setEnabled(False)
        self.worker.start()

    def _start_video(self) -> None:
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.worker.start_stream()

    def _stop_video(self) -> None:
        self.stop_button.setEnabled(False)
        self.worker.stop_stream()

    def _on_status_changed(self, status: str) -> None:
        self.status_label.setText(status)
        connected = status in ("Connected", "Starting video...", "Video streaming")
        self.connect_button.setEnabled(not connected and not self.worker.isRunning())
        self.start_button.setEnabled(status == "Connected")
        if status != "Video streaming":
            self.stop_button.setEnabled(False)
        elif status == "Video streaming":
            self.stop_button.setEnabled(True)

    def _on_frame_ready(self, image: QImage) -> None:
        pixmap = QPixmap.fromImage(image).scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(pixmap)

    def _on_worker_finished(self) -> None:
        self.connect_button.setEnabled(True)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)

    def closeEvent(self, event) -> None:
        if self.worker.isRunning():
            self.worker.shutdown()
            self.worker.wait(3000)
        event.accept()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Tello EDU video preview.")
    parser.add_argument(
        "--local-ip",
        help="Local PC IP on the Tello Wi-Fi adapter, for example 192.168.10.2.",
    )
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    window = VideoPreviewWindow(args.local_ip)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
