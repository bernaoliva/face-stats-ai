from __future__ import annotations

import logging

import cv2
import numpy as np
from facenet_pytorch import MTCNN
import torch

logger = logging.getLogger(__name__)


class FaceDetector:
    def __init__(self, min_confidence: float = 0.9) -> None:
        self._min_confidence = min_confidence
        self._mtcnn = MTCNN(
            keep_all=True,
            device=torch.device("cpu"),
            min_face_size=60,
            thresholds=[0.6, 0.7, 0.7],
        )

    def detect_faces(
        self, frame: np.ndarray,
    ) -> list[tuple[np.ndarray, float, list[int]]]:
        """Detect faces in frame.

        Args:
            frame: BGR image (HxWx3).

        Returns:
            List of (cropped_face_bgr, confidence, [x1, y1, x2, y2]).
        """
        # MTCNN expects RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        boxes, probs = self._mtcnn.detect(rgb)

        if boxes is None or probs is None:
            return []

        results: list[tuple[np.ndarray, float, list[int]]] = []
        h, w = frame.shape[:2]

        for box, prob in zip(boxes, probs):
            if prob < self._min_confidence:
                continue

            x1, y1, x2, y2 = box.astype(int)

            # Add 20% margin
            bw = x2 - x1
            bh = y2 - y1
            margin_x = int(bw * 0.2)
            margin_y = int(bh * 0.2)

            x1 = max(0, x1 - margin_x)
            y1 = max(0, y1 - margin_y)
            x2 = min(w, x2 + margin_x)
            y2 = min(h, y2 + margin_y)

            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            results.append((crop, float(prob), [x1, y1, x2, y2]))

        return results
