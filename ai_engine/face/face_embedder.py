import os
import cv2 as cv
import numpy as np

# Suppress TensorFlow logging warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

class FaceEmbedder:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(FaceEmbedder, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        from keras_facenet import FaceNet
        self.embedder = FaceNet()
        self.target_size = (160, 160)
        self._initialized = True

    def generate_embedding(self, face_bgr: np.ndarray) -> np.ndarray:
        """
        Extracts normalized 512-dimensional FaceNet embedding from a cropped BGR face image.
        """
        if face_bgr is None or face_bgr.size == 0 or face_bgr.shape[0] < 10 or face_bgr.shape[1] < 10:
            return None
        
        try:
            face_rgb = cv.cvtColor(face_bgr, cv.COLOR_BGR2RGB)
            face_resized = cv.resize(face_rgb, self.target_size)
            face_float = face_resized.astype('float32')
            face_input = np.expand_dims(face_float, axis=0)

            raw_embedding = self.embedder.embeddings(face_input)[0]
            
            # L2 Normalization
            norm = np.linalg.norm(raw_embedding)
            if norm > 0:
                normalized_embedding = raw_embedding / norm
            else:
                normalized_embedding = raw_embedding

            return normalized_embedding
        except Exception as e:
            print(f"[FaceEmbedder] Error generating embedding: {e}")
            return None
