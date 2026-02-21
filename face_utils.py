"""Face recognition utilities.

Uses the `face_recognition` library (dlib-based) for:
- Encoding a face from an image/frame.
- Comparing an unknown encoding against a list of known encodings.
"""
import pickle
import numpy as np

try:
    import face_recognition
    _FR_AVAILABLE = True
except ImportError:  # pragma: no cover – optional at runtime
    _FR_AVAILABLE = False

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CV2_AVAILABLE = False

TOLERANCE = 0.55  # lower = stricter match


def encode_face_from_bytes(image_bytes: bytes) -> bytes | None:
    """Return a pickled numpy face-encoding from raw image bytes, or None if
    no face is detected."""
    if not _FR_AVAILABLE:
        raise RuntimeError("face_recognition library is not installed.")
    import face_recognition as fr
    img = fr.load_image_file(__import__("io").BytesIO(image_bytes))
    encodings = fr.face_encodings(img)
    if not encodings:
        return None
    return pickle.dumps(encodings[0])


def encode_face_from_path(image_path: str) -> bytes | None:
    """Return a pickled numpy face-encoding from an image file path."""
    with open(image_path, "rb") as fh:
        return encode_face_from_bytes(fh.read())


def decode_encoding(blob: bytes) -> np.ndarray:
    """Unpickle a stored face encoding blob back to a numpy array."""
    return pickle.loads(blob)


def identify_face(
    frame_bytes: bytes,
    known_encodings: list,
    known_ids: list,
) -> int | None:
    """Identify a face in *frame_bytes* against *known_encodings*.

    Parameters
    ----------
    frame_bytes:
        Raw JPEG/PNG bytes of the camera frame.
    known_encodings:
        List of numpy arrays (one per registered student).
    known_ids:
        Parallel list of student row-IDs (int).

    Returns
    -------
    The matched student DB row-ID, or None if no match.
    """
    if not _FR_AVAILABLE:
        raise RuntimeError("face_recognition library is not installed.")
    import face_recognition as fr

    img = fr.load_image_file(__import__("io").BytesIO(frame_bytes))
    unknown_encodings = fr.face_encodings(img)
    if not unknown_encodings:
        return None

    for unknown_enc in unknown_encodings:
        distances = fr.face_distance(known_encodings, unknown_enc)
        if len(distances) == 0:
            continue
        best_idx = int(np.argmin(distances))
        if distances[best_idx] <= TOLERANCE:
            return known_ids[best_idx]
    return None


def draw_face_boxes(frame_bytes: bytes) -> bytes:
    """Return JPEG bytes with face bounding-boxes drawn on the frame.
    Used for the live attendance capture preview."""
    if not _FR_AVAILABLE or not _CV2_AVAILABLE:
        return frame_bytes
    import face_recognition as fr
    import cv2 as _cv2

    img = fr.load_image_file(__import__("io").BytesIO(frame_bytes))
    locations = fr.face_locations(img)
    img_bgr = _cv2.cvtColor(img, _cv2.COLOR_RGB2BGR)
    for top, right, bottom, left in locations:
        _cv2.rectangle(img_bgr, (left, top), (right, bottom), (0, 200, 0), 2)
    _, buf = _cv2.imencode(".jpg", img_bgr)
    return buf.tobytes()
