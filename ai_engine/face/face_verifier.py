import os
import time
import json
import numpy as np
from typing import Dict, Any, Optional
from db.database import SessionLocal
from db.models import CollegeMember, FaceEmbedding, SystemSetting

DEFAULT_SIMILARITY_THRESHOLD = float(os.getenv("FACE_VERIFICATION_THRESHOLD", "0.60"))

class FaceVerifier:
    def __init__(self, threshold: float = DEFAULT_SIMILARITY_THRESHOLD):
        self.threshold = threshold
        self._threshold_last_refresh = 0.0
        self._embeddings_last_refresh = 0.0
        self.enrolled_cache = []
        self.load_error = None
        self.reload_enrolled_embeddings()

    def reload_enrolled_embeddings(self):
        """
        Loads all active enrolled face embeddings from the database into memory cache.
        """
        db = SessionLocal()
        try:
            threshold_setting = db.query(SystemSetting).filter(SystemSetting.key == "FACE_VERIFICATION_THRESHOLD").first()
            if threshold_setting:
                self.threshold = float(threshold_setting.value)
            members = db.query(CollegeMember).filter(
                CollegeMember.status == "ACTIVE",
                CollegeMember.face_enrolled == True
            ).all()

            cache = []
            for member in members:
                for emb_obj in member.embeddings:
                    emb_vec = np.array(json.loads(emb_obj.embedding_json), dtype=np.float32)
                    # Normalize if not normalized
                    norm = np.linalg.norm(emb_vec)
                    if norm > 0:
                        emb_vec = emb_vec / norm
                    cache.append({
                        "member_id": member.id,
                        "name": member.name,
                        "role": member.role,
                        "college_id": member.college_id,
                        "department": member.department,
                        "embedding": emb_vec
                    })
            self.enrolled_cache = cache
            self.load_error = None
            self._embeddings_last_refresh = time.monotonic()
            print(f"[FaceVerifier] Loaded {len(self.enrolled_cache)} enrolled face embedding(s).")
        except Exception as e:
            print(f"[FaceVerifier] Error reloading embeddings: {e}")
            self.enrolled_cache = []
            self.load_error = str(e)
        finally:
            db.close()

    def verify_embedding(self, query_embedding: np.ndarray) -> Dict[str, Any]:
        """
        Compares query 512-d embedding against enrolled embeddings using Cosine Similarity.
        Returns verification result dictionary.
        """
        if time.monotonic() - self._embeddings_last_refresh > 10:
            self.reload_enrolled_embeddings()
        if time.monotonic() - self._threshold_last_refresh > 5:
            db = SessionLocal()
            try:
                setting = db.query(SystemSetting).filter(SystemSetting.key == "FACE_VERIFICATION_THRESHOLD").first()
                if setting:
                    self.threshold = float(setting.value)
                self._threshold_last_refresh = time.monotonic()
            except (TypeError, ValueError):
                pass
            finally:
                db.close()

        if self.load_error:
            raise RuntimeError(f"Could not load enrolled face embeddings: {self.load_error}")
        if query_embedding is None or len(self.enrolled_cache) == 0:
            return {
                "status": "UNKNOWN",
                "member_id": None,
                "name": None,
                "role": None,
                "similarity": 0.0
            }

        # Normalize query vector
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_vec = query_embedding / norm
        else:
            query_vec = query_embedding

        best_match = None
        best_similarity = -1.0

        for enrolled in self.enrolled_cache:
            similarity = float(np.dot(query_vec, enrolled["embedding"]))
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = enrolled

        if best_match is not None and best_similarity >= self.threshold:
            return {
                "status": "VERIFIED",
                "member_id": best_match["member_id"],
                "name": best_match["name"],
                "role": best_match["role"],
                "college_id": best_match["college_id"],
                "department": best_match["department"],
                "similarity": round(best_similarity, 4)
            }
        else:
            return {
                "status": "UNKNOWN" if best_match is None else "UNVERIFIED",
                "member_id": None,
                "name": None,
                "role": None,
                "college_id": None,
                "department": None,
                "similarity": round(max(0.0, best_similarity), 4)
            }
