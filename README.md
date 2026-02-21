# Face Attendance System – SIH 2025

**Automated Attendance System** | Smart India Hackathon 2025 | Python · Flask · MySQL · Bootstrap · SMTP

> Automated attendance tracking for 1,000+ student records. Reduces manual attendance time from **2 minutes to ~15 seconds** per class using real-time face recognition.

---

## Features

| Feature | Details |
|---|---|
| **Face Recognition** | dlib-based 128-d face encoding; identifies registered students from a live webcam feed |
| **Automated attendance** | One-click scanning marks present/absent in the MySQL database |
| **Manual fallback** | Bulk manual entry screen for situations where the camera is unavailable |
| **SMTP email reports** | Daily attendance summary sent to the class teacher; low-attendance alerts (<75 %) sent to individual students |
| **Dashboard** | Real-time stats – total students, classes, today's attendance |
| **Scalable DB** | MySQL schema supports 1,000+ student records with indexed queries |

---

## Tech Stack

- **Backend** – Python 3.12, Flask 3
- **Database** – MySQL 8 (`mysql-connector-python`)
- **Face Recognition** – `face_recognition` (dlib) + OpenCV
- **Frontend** – Bootstrap 5, Bootstrap Icons
- **Email** – Python `smtplib` (SMTP/STARTTLS)

---

## Project Structure

```
face-attendance-system-sih/
├── app.py                  # Flask application & all routes
├── config.py               # Configuration (env-var driven)
├── db.py                   # MySQL connection pool helper
├── face_utils.py           # Face encoding & identification
├── email_service.py        # SMTP email notifications
├── schema.sql              # MySQL DDL (run once to set up DB)
├── requirements.txt        # Python dependencies
├── .env.example            # Sample environment file
├── tests.py                # Unit tests (pytest)
├── templates/              # Jinja2 / Bootstrap HTML templates
│   ├── base.html
│   ├── index.html          # Dashboard
│   ├── classes.html / add_class.html
│   ├── students.html / register.html
│   ├── attendance.html     # Live face-recognition attendance
│   ├── records.html        # View / filter attendance records
│   ├── manual_attendance.html
│   └── reports.html        # Email reporting
└── static/
    ├── css/style.css
    └── js/main.js
```

---

## Quick Start

### 1. Clone & install dependencies

```bash
git clone https://github.com/Adithyanusum/face-attendance-system-sih.git
cd face-attendance-system-sih
pip install -r requirements.txt
```

> `face_recognition` requires **cmake** and **dlib**. On Ubuntu:
> ```bash
> sudo apt-get install cmake libboost-all-dev
> pip install dlib face_recognition
> ```

### 2. Set up MySQL

```bash
mysql -u root -p < schema.sql
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your DB credentials and SMTP settings
```

### 4. Run

```bash
python app.py
# Open http://localhost:5000
```

---

## Running Tests

```bash
pytest tests.py -v
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | MySQL connection |
| `SECRET_KEY` | Flask session secret (change in production) |
| `SMTP_HOST` / `SMTP_PORT` | SMTP server (default: Gmail, port 587) |
| `SMTP_USER` / `SMTP_PASSWORD` | SMTP login credentials |
| `SMTP_FROM` / `SMTP_FROM_NAME` | Sender address shown in emails |
| `ADMIN_EMAIL` | Admin notification address |

---

## Workflow

1. **Add classes** – Create subjects with teacher email addresses.
2. **Register students** – Capture a face photo via webcam; encoding is stored in MySQL.
3. **Mark attendance** – Open *Mark Attendance*, select class, click *Start Scanning*. The system identifies faces every 2 seconds and marks students as present.
4. **View records** – Filter by class and date to review attendance.
5. **Send reports** – Email daily summaries to teachers or low-attendance alerts to students with one click.

