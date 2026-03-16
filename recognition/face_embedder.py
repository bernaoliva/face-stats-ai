from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


class FaceEmbedder:
    def __init__(self, use_gpu: bool = True) -> None:
        import insightface
        from insightface.app import FaceAnalysis

        providers: list[str] = []
        if use_gpu:
            providers.append("CUDAExecutionProvider")
        providers.append("CPUExecutionProvider")

        self._app = FaceAnalysis(
            name="buffalo_l",
            providers=providers,
        )
        self._app.prepare(ctx_id=0 if use_gpu else -1, det_size=(640, 640))
        logger.info("FaceEmbedder initialized with providers: %s", providers)

    def get_embedding(self, face_image: np.ndarray) -> np.ndarray | None:
        """Extract 512-dim L2-normalized embedding from a face image.

        Args:
            face_image: BGR image (HxWx3) containing a face.

        Returns:
            512-dim normalized embedding or None if no face detected.
        """
        faces = self._app.get(face_image)
        if not faces:
            logger.debug("No face detected in image")
            return None

        # Use the face with highest detection score
        best_face = max(faces, key=lambda f: f.det_score)
        embedding = best_face.normed_embedding  # already L2-normalized by insightface

        if embedding is None:
            return None

        # Ensure normalization
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding
