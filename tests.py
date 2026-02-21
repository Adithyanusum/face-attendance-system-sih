"""Unit tests for the face attendance system (no DB or camera required)."""
import io
import json
import base64
import pickle
import unittest
from unittest.mock import patch, MagicMock

import numpy as np


class TestFaceUtils(unittest.TestCase):
    """Tests for face_utils module."""

    def test_decode_encoding_roundtrip(self):
        """encode -> pickle -> decode should round-trip correctly."""
        from face_utils import decode_encoding
        original = np.array([0.1] * 128)
        blob = pickle.dumps(original)
        decoded = decode_encoding(blob)
        np.testing.assert_array_almost_equal(original, decoded)

    def test_identify_face_no_match(self):
        """identify_face should return None when distance exceeds tolerance."""
        import face_utils

        enc_known = np.zeros(128)
        enc_unknown = np.ones(128)

        # Stub face_recognition so no actual dlib needed
        mock_fr = MagicMock()
        mock_fr.load_image_file.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_fr.face_encodings.return_value = [enc_unknown]
        mock_fr.face_distance.return_value = np.array([1.0])  # > TOLERANCE

        with patch.dict("sys.modules", {"face_recognition": mock_fr}):
            face_utils._FR_AVAILABLE = True
            result = face_utils.identify_face(b"fake", [enc_known], [1])

        self.assertIsNone(result)

    def test_identify_face_match(self):
        """identify_face should return the matching student id."""
        import face_utils

        enc_known = np.zeros(128)
        enc_unknown = np.zeros(128)  # identical → distance 0

        mock_fr = MagicMock()
        mock_fr.load_image_file.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_fr.face_encodings.return_value = [enc_unknown]
        mock_fr.face_distance.return_value = np.array([0.0])  # perfect match

        with patch.dict("sys.modules", {"face_recognition": mock_fr}):
            face_utils._FR_AVAILABLE = True
            result = face_utils.identify_face(b"fake", [enc_known], [42])

        self.assertEqual(result, 42)

    def test_encode_face_from_bytes_no_face(self):
        """encode_face_from_bytes should return None when no face is detected."""
        import face_utils

        mock_fr = MagicMock()
        mock_fr.load_image_file.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_fr.face_encodings.return_value = []  # no face

        with patch.dict("sys.modules", {"face_recognition": mock_fr}):
            face_utils._FR_AVAILABLE = True
            result = face_utils.encode_face_from_bytes(b"fake_image_bytes")

        self.assertIsNone(result)

    def test_draw_face_boxes_returns_bytes(self):
        """draw_face_boxes should return bytes (passthrough when no cv2/fr)."""
        import face_utils

        enc_frame = b"fake_frame_bytes"
        mock_fr = MagicMock()
        mock_fr.load_image_file.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_fr.face_locations.return_value = [(10, 80, 60, 20)]  # one face box

        mock_cv2 = MagicMock()
        encoded_buf = MagicMock()
        encoded_buf.tobytes.return_value = b"encoded_jpeg"
        mock_cv2.imencode.return_value = (True, encoded_buf)
        mock_cv2.cvtColor.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cv2.COLOR_RGB2BGR = 4

        with patch.dict("sys.modules", {"face_recognition": mock_fr, "cv2": mock_cv2}):
            face_utils._FR_AVAILABLE = True
            face_utils._CV2_AVAILABLE = True
            result = face_utils.draw_face_boxes(enc_frame)

        self.assertEqual(result, b"encoded_jpeg")

    def test_draw_face_boxes_fallback_when_unavailable(self):
        """draw_face_boxes should return input bytes unchanged when libs missing."""
        import face_utils

        original_fr = face_utils._FR_AVAILABLE
        original_cv2 = face_utils._CV2_AVAILABLE
        face_utils._FR_AVAILABLE = False
        face_utils._CV2_AVAILABLE = False
        try:
            result = face_utils.draw_face_boxes(b"raw_bytes")
            self.assertEqual(result, b"raw_bytes")
        finally:
            face_utils._FR_AVAILABLE = original_fr
            face_utils._CV2_AVAILABLE = original_cv2


        """encode_face_from_bytes should return pickled bytes when a face is found."""
        import face_utils

        enc = np.array([0.5] * 128)
        mock_fr = MagicMock()
        mock_fr.load_image_file.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_fr.face_encodings.return_value = [enc]

        with patch.dict("sys.modules", {"face_recognition": mock_fr}):
            face_utils._FR_AVAILABLE = True
            result = face_utils.encode_face_from_bytes(b"fake_image_bytes")

        self.assertIsNotNone(result)
        decoded = pickle.loads(result)
        np.testing.assert_array_almost_equal(enc, decoded)


class TestEmailService(unittest.TestCase):
    """Tests for email_service module."""

    def test_send_email_no_credentials(self):
        """send_email should return False when SMTP creds are not configured."""
        from email_service import send_email
        from config import Config
        original_user = Config.SMTP_USER
        original_password = Config.SMTP_PASSWORD
        Config.SMTP_USER = ""
        Config.SMTP_PASSWORD = ""
        try:
            result = send_email("test@example.com", "Subject", "<p>Body</p>")
            self.assertFalse(result)
        finally:
            Config.SMTP_USER = original_user
            Config.SMTP_PASSWORD = original_password

    @patch("smtplib.SMTP")
    def test_send_email_success(self, mock_smtp_cls):
        """send_email should return True and call SMTP methods on success."""
        from email_service import send_email
        from config import Config

        # Configure fake credentials
        Config.SMTP_USER = "user@example.com"
        Config.SMTP_PASSWORD = "password"
        Config.SMTP_FROM = "user@example.com"

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        # Patch DB log to avoid needing a real DB
        with patch("email_service._log_email"):
            result = send_email("recipient@example.com", "Test Subject", "<p>Hello</p>")

        self.assertTrue(result)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()

    def test_send_daily_report_builds_html(self):
        """send_daily_report should call send_email with correct subject."""
        from email_service import send_daily_report
        from datetime import date

        report_rows = [
            {"student_id": "S001", "name": "Alice", "status": "present"},
            {"student_id": "S002", "name": "Bob", "status": "absent"},
        ]

        with patch("email_service.send_email", return_value=True) as mock_send:
            result = send_daily_report(
                "teacher@example.com", "CSE-A – DS", report_rows,
                date(2025, 1, 15)
            )

        self.assertTrue(result)
        call_args = mock_send.call_args
        self.assertIn("15 Jan 2025", call_args[0][1])   # subject has date
        self.assertIn("Alice", call_args[0][2])          # body has student name
        self.assertIn("Bob", call_args[0][2])

    def test_send_low_attendance_alert(self):
        """send_low_attendance_alert should include percentage in body."""
        from email_service import send_low_attendance_alert

        with patch("email_service.send_email", return_value=True) as mock_send:
            result = send_low_attendance_alert(
                "student@example.com", "Alice", "CSE-A – DS", 60.0
            )

        self.assertTrue(result)
        body = mock_send.call_args[0][2]
        self.assertIn("60.0%", body)
        self.assertIn("Alice", body)


class TestFlaskRoutes(unittest.TestCase):
    """Smoke tests for Flask routes (no DB required)."""

    def setUp(self):
        from app import app
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()
        # Patch all DB queries to return empty defaults
        self.db_patcher = patch("app._safe_query", return_value=[])
        self.db_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()

    def test_index_returns_200(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Dashboard", resp.data)

    def test_students_list(self):
        resp = self.client.get("/students")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Students", resp.data)

    def test_register_student_get(self):
        resp = self.client.get("/students/register")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Register Student", resp.data)

    def test_classes_page(self):
        resp = self.client.get("/classes")
        self.assertEqual(resp.status_code, 200)

    def test_attendance_page(self):
        resp = self.client.get("/attendance")
        self.assertEqual(resp.status_code, 200)

    def test_records_page(self):
        resp = self.client.get("/attendance/records")
        self.assertEqual(resp.status_code, 200)

    def test_reports_page(self):
        resp = self.client.get("/reports")
        self.assertEqual(resp.status_code, 200)

    def test_mark_attendance_missing_params(self):
        """POST /attendance/mark with missing params returns JSON error."""
        resp = self.client.post(
            "/attendance/mark",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertFalse(data["success"])

    def test_mark_attendance_no_encodings(self):
        """POST /attendance/mark with valid params but no encodings in DB."""
        frame = base64.b64encode(b"fake_frame").decode()
        resp = self.client.post(
            "/attendance/mark",
            data=json.dumps({"frame": frame, "class_id": "1"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertFalse(data["success"])
        self.assertIn("No registered faces", data["message"])


if __name__ == "__main__":
    unittest.main()
