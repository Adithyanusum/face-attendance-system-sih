"""Configuration settings loaded from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

    # Database
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 3306))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "attendance_db")

    # SMTP
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", ""))
    SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Attendance System")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

    # Upload folder for captured face images
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "face_data")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
