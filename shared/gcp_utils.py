from __future__ import annotations

import os
from functools import lru_cache

from google.cloud import firestore, storage
from google import genai


@lru_cache(maxsize=1)
def get_firestore_client() -> firestore.Client:
    return firestore.Client(project=os.getenv("GCP_PROJECT_ID"))


@lru_cache(maxsize=1)
def get_gcs_client() -> storage.Client:
    return storage.Client(project=os.getenv("GCP_PROJECT_ID"))


@lru_cache(maxsize=1)
def get_genai_client() -> genai.Client:
    return genai.Client()
