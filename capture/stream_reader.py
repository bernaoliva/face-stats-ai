from __future__ import annotations

import logging
import time

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class StreamReader:
    def __init__(self, source: str, ndi_name: str = "", rtmp_url: str = "") -> None:
        self._source = source
        self._cap: cv2.VideoCapture | None = None
        self._ndi_recv = None

        if source == "ndi":
            self._init_ndi(ndi_name)
        else:
            self._init_rtmp(rtmp_url)

    def _init_ndi(self, ndi_name: str) -> None:
        try:
            import NDIlib as ndi

            if not ndi.initialize():
                raise RuntimeError("NDI failed to initialize")

            finder = ndi.find_create_v2()
            if not finder:
                raise RuntimeError("NDI finder creation failed")

            # Wait for sources
            ndi.find_wait_for_sources(finder, timeout_in_ms=5000)
            sources = ndi.find_get_current_sources(finder)

            target = None
            for src in sources:
                if ndi_name.lower() in src.ndi_name.lower():
                    target = src
                    break

            if target is None:
                raise RuntimeError(f"NDI source '{ndi_name}' not found. Available: {[s.ndi_name for s in sources]}")

            recv_settings = ndi.RecvCreateV3()
            recv_settings.color_format = ndi.RECV_COLOR_FORMAT_BGRX_BGRA
            self._ndi_recv = ndi.recv_create_v3(recv_settings)
            ndi.recv_connect(self._ndi_recv, target)
            ndi.find_destroy(finder)

            logger.info("Connected to NDI source: %s", target.ndi_name)
        except ImportError:
            logger.warning("NDI not available, falling back to RTMP")
            self._source = "rtmp"
            self._init_rtmp("")

    def _init_rtmp(self, rtmp_url: str) -> None:
        if not rtmp_url:
            logger.warning("No RTMP URL provided")
            return
        self._cap = cv2.VideoCapture(rtmp_url)
        if not self._cap.isOpened():
            logger.error("Failed to open RTMP stream: %s", rtmp_url)
            self._cap = None
        else:
            logger.info("Connected to RTMP stream: %s", rtmp_url)

    def read_frame(self) -> np.ndarray | None:
        if self._source == "ndi":
            return self._read_ndi()
        return self._read_rtmp()

    def _read_ndi(self) -> np.ndarray | None:
        try:
            import NDIlib as ndi

            if self._ndi_recv is None:
                return None

            frame_type, video_frame, _, _ = ndi.recv_capture_v2(
                self._ndi_recv, timeout_in_ms=1000,
            )
            if frame_type == ndi.FRAME_TYPE_VIDEO:
                frame = np.copy(video_frame.data)
                ndi.recv_free_video_v2(self._ndi_recv, video_frame)
                # Convert BGRX to BGR
                if frame.shape[2] == 4:
                    frame = frame[:, :, :3]
                return frame
        except Exception:
            logger.warning("NDI frame read failed", exc_info=True)
        return None

    def _read_rtmp(self) -> np.ndarray | None:
        if self._cap is None or not self._cap.isOpened():
            return None
        ret, frame = self._cap.read()
        if not ret:
            return None
        return frame

    def release(self) -> None:
        if self._cap:
            self._cap.release()
        if self._ndi_recv:
            try:
                import NDIlib as ndi
                ndi.recv_destroy(self._ndi_recv)
                ndi.destroy()
            except Exception:
                pass
