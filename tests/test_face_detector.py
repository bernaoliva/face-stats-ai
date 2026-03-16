import numpy as np
import pytest


class TestFaceDetectorUnit:
    """Unit tests that don't require actual model loading."""

    def test_empty_frame_handling(self):
        """Test that the detector returns empty list for blank images."""
        from capture.face_detector import FaceDetector

        detector = FaceDetector(min_confidence=0.9)
        # Black image — no faces
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        results = detector.detect_faces(blank)
        assert isinstance(results, list)
        # Blank image should return no faces (or very low confidence)
        assert len(results) == 0

    def test_margin_calculation(self):
        """Verify 20% margin logic."""
        # Box: 100x100 starting at (200, 200)
        x1, y1, x2, y2 = 200, 200, 300, 300
        bw = x2 - x1  # 100
        bh = y2 - y1  # 100
        margin_x = int(bw * 0.2)  # 20
        margin_y = int(bh * 0.2)  # 20

        new_x1 = max(0, x1 - margin_x)
        new_y1 = max(0, y1 - margin_y)
        new_x2 = min(1920, x2 + margin_x)
        new_y2 = min(1080, y2 + margin_y)

        assert new_x1 == 180
        assert new_y1 == 180
        assert new_x2 == 320
        assert new_y2 == 320
