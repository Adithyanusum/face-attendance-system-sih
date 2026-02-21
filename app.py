"""Main Flask application – Automated Face Attendance System (SIH 2025)."""
import os
import io
import base64
import logging
from datetime import date, datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    Response,
)
from werkzeug.utils import secure_filename

from config import Config
from email_service import send_daily_report, send_low_attendance_alert

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# ---------------------------------------------------------------------------
# DB helpers (lazy – gracefully degrades when MySQL is unavailable)
# ---------------------------------------------------------------------------

def _db():
    from db import execute_query
    return execute_query


def _safe_query(query, params=None, fetch=True, default=None):
    try:
        from db import execute_query
        return execute_query(query, params, fetch=fetch)
    except Exception as exc:
        logger.warning("DB query failed: %s", exc)
        return default if default is not None else ([] if fetch else None)


# ---------------------------------------------------------------------------
# Face-encoding helpers
# ---------------------------------------------------------------------------

def _load_known_encodings():
    """Load all registered face encodings from the DB into memory."""
    rows = _safe_query(
        "SELECT id, face_encoding FROM students WHERE face_encoding IS NOT NULL",
        default=[],
    )
    known_encodings, known_ids = [], []
    for row in rows:
        try:
            from face_utils import decode_encoding
            enc = decode_encoding(row["face_encoding"])
            known_encodings.append(enc)
            known_ids.append(row["id"])
        except Exception:
            pass
    return known_encodings, known_ids


# ---------------------------------------------------------------------------
# Routes – Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    total_students = (_safe_query("SELECT COUNT(*) AS c FROM students", default=[{"c": 0}]) or [{"c": 0}])[0]["c"]
    total_classes = (_safe_query("SELECT COUNT(*) AS c FROM classes", default=[{"c": 0}]) or [{"c": 0}])[0]["c"]
    today_attendance = (_safe_query(
        "SELECT COUNT(*) AS c FROM attendance WHERE date = %s AND status = 'present'",
        (date.today(),), default=[{"c": 0}]
    ) or [{"c": 0}])[0]["c"]
    recent_attendance = _safe_query(
        "SELECT a.id, s.name, s.student_id, c.name AS class_name, "
        "a.date, a.time, a.status, a.marked_by "
        "FROM attendance a "
        "JOIN students s ON s.id = a.student_id "
        "JOIN classes c ON c.id = a.class_id "
        "ORDER BY a.created_at DESC LIMIT 10",
        default=[],
    )
    return render_template(
        "index.html",
        total_students=total_students,
        total_classes=total_classes,
        today_attendance=today_attendance,
        recent_attendance=recent_attendance,
    )


# ---------------------------------------------------------------------------
# Routes – Classes
# ---------------------------------------------------------------------------

@app.route("/classes")
def classes():
    rows = _safe_query(
        "SELECT c.*, COUNT(s.id) AS student_count "
        "FROM classes c LEFT JOIN students s ON s.class_id = c.id "
        "GROUP BY c.id ORDER BY c.name",
        default=[],
    )
    return render_template("classes.html", classes=rows)


@app.route("/classes/add", methods=["GET", "POST"])
def add_class():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        subject = request.form.get("subject", "").strip()
        teacher_name = request.form.get("teacher_name", "").strip()
        teacher_email = request.form.get("teacher_email", "").strip()
        if not name or not subject:
            flash("Class name and subject are required.", "danger")
        else:
            _safe_query(
                "INSERT INTO classes (name, subject, teacher_name, teacher_email) "
                "VALUES (%s, %s, %s, %s)",
                (name, subject, teacher_name, teacher_email),
                fetch=False,
            )
            flash(f"Class '{name}' added successfully.", "success")
            return redirect(url_for("classes"))
    return render_template("add_class.html")


# ---------------------------------------------------------------------------
# Routes – Students
# ---------------------------------------------------------------------------

@app.route("/students")
def students():
    class_id = request.args.get("class_id")
    search = request.args.get("q", "").strip()
    params = []
    query = (
        "SELECT s.id, s.student_id, s.name, s.email, c.name AS class_name, "
        "s.created_at, s.face_encoding IS NOT NULL AS has_face "
        "FROM students s LEFT JOIN classes c ON c.id = s.class_id "
    )
    conditions = []
    if class_id:
        conditions.append("s.class_id = %s")
        params.append(int(class_id))
    if search:
        conditions.append("(s.name LIKE %s OR s.student_id LIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])
    if conditions:
        query += "WHERE " + " AND ".join(conditions) + " "
    query += "ORDER BY s.name LIMIT 200"

    rows = _safe_query(query, params or None, default=[])
    all_classes = _safe_query("SELECT id, name FROM classes ORDER BY name", default=[])
    return render_template("students.html", students=rows, classes=all_classes,
                           selected_class=class_id, search=search)


@app.route("/students/register", methods=["GET", "POST"])
def register_student():
    all_classes = _safe_query("SELECT id, name FROM classes ORDER BY name", default=[])
    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        class_id = request.form.get("class_id") or None
        face_image_b64 = request.form.get("face_image", "")

        if not student_id or not name:
            flash("Student ID and name are required.", "danger")
            return render_template("register.html", classes=all_classes)

        # Check duplicate
        existing = _safe_query(
            "SELECT id FROM students WHERE student_id = %s", (student_id,), default=[]
        )
        if existing:
            flash(f"Student ID '{student_id}' already exists.", "danger")
            return render_template("register.html", classes=all_classes)

        face_encoding_blob = None
        photo_path = None

        if face_image_b64:
            try:
                # Strip data URI prefix if present
                if "," in face_image_b64:
                    face_image_b64 = face_image_b64.split(",", 1)[1]
                image_bytes = base64.b64decode(face_image_b64)

                # Save photo
                filename = secure_filename(f"{student_id}.jpg")
                photo_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                with open(photo_path, "wb") as fh:
                    fh.write(image_bytes)

                from face_utils import encode_face_from_bytes
                face_encoding_blob = encode_face_from_bytes(image_bytes)
                if face_encoding_blob is None:
                    flash("No face detected in the captured image. Student saved without face data.", "warning")
            except Exception as exc:
                logger.exception("Face encoding failed for student %s", student_id)
                flash(f"Face encoding failed: {exc}. Student saved without face data.", "warning")

        _safe_query(
            "INSERT INTO students (student_id, name, email, class_id, face_encoding, photo_path) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (student_id, name, email or None, class_id, face_encoding_blob,
             os.path.basename(photo_path) if photo_path else None),
            fetch=False,
        )
        flash(f"Student '{name}' registered successfully.", "success")
        return redirect(url_for("students"))

    return render_template("register.html", classes=all_classes)


@app.route("/students/<int:student_db_id>/delete", methods=["POST"])
def delete_student(student_db_id):
    _safe_query("DELETE FROM students WHERE id = %s", (student_db_id,), fetch=False)
    flash("Student deleted.", "info")
    return redirect(url_for("students"))


# ---------------------------------------------------------------------------
# Routes – Attendance
# ---------------------------------------------------------------------------

@app.route("/attendance")
def attendance():
    all_classes = _safe_query("SELECT id, name, subject FROM classes ORDER BY name", default=[])
    return render_template("attendance.html", classes=all_classes)


@app.route("/attendance/mark", methods=["POST"])
def mark_attendance():
    """API endpoint – receives a base64 JPEG frame from the webcam, identifies
    the student via face recognition, and records attendance."""
    data = request.get_json(force=True) or {}
    frame_b64 = data.get("frame", "")
    class_id = data.get("class_id")
    marked_by = data.get("marked_by", "face")

    if not frame_b64 or not class_id:
        return jsonify({"success": False, "message": "Missing frame or class_id."})

    if "," in frame_b64:
        frame_b64 = frame_b64.split(",", 1)[1]

    try:
        frame_bytes = base64.b64decode(frame_b64)
    except Exception:
        return jsonify({"success": False, "message": "Invalid image data."})

    if marked_by == "face":
        known_encodings, known_ids = _load_known_encodings()
        if not known_encodings:
            return jsonify({"success": False, "message": "No registered faces found."})

        try:
            from face_utils import identify_face
            student_db_id = identify_face(frame_bytes, known_encodings, known_ids)
        except RuntimeError as exc:
            return jsonify({"success": False, "message": str(exc)})

        if student_db_id is None:
            return jsonify({"success": False, "message": "Face not recognised."})
    else:
        student_db_id = data.get("student_db_id")
        if not student_db_id:
            return jsonify({"success": False, "message": "student_db_id required for manual marking."})

    # Fetch student info
    student_rows = _safe_query(
        "SELECT id, name, student_id FROM students WHERE id = %s", (student_db_id,), default=[]
    )
    if not student_rows:
        return jsonify({"success": False, "message": "Student not found."})
    student = student_rows[0]

    today = date.today()
    now_time = datetime.now().time()

    # Upsert attendance (ignore if already marked today for this class)
    try:
        _safe_query(
            "INSERT IGNORE INTO attendance (student_id, class_id, date, time, status, marked_by) "
            "VALUES (%s, %s, %s, %s, 'present', %s)",
            (student_db_id, class_id, today, now_time, marked_by),
            fetch=False,
        )
    except Exception as exc:
        return jsonify({"success": False, "message": f"DB error: {exc}"})

    return jsonify({
        "success": True,
        "message": f"Attendance marked for {student['name']} ({student['student_id']})",
        "student": {"name": student["name"], "student_id": student["student_id"]},
    })


@app.route("/attendance/records")
def attendance_records():
    selected_class = request.args.get("class_id")
    selected_date = request.args.get("date", date.today().isoformat())
    all_classes = _safe_query("SELECT id, name, subject FROM classes ORDER BY name", default=[])

    records = []
    if selected_class:
        records = _safe_query(
            "SELECT s.name, s.student_id, a.time, a.status, a.marked_by "
            "FROM attendance a "
            "JOIN students s ON s.id = a.student_id "
            "WHERE a.class_id = %s AND a.date = %s "
            "ORDER BY s.name",
            (selected_class, selected_date),
            default=[],
        )

    return render_template(
        "records.html",
        classes=all_classes,
        records=records,
        selected_class=selected_class,
        selected_date=selected_date,
    )


@app.route("/attendance/manual", methods=["GET", "POST"])
def manual_attendance():
    """Mark attendance manually (fallback when face recognition fails)."""
    all_classes = _safe_query("SELECT id, name, subject FROM classes ORDER BY name", default=[])
    students_list = _safe_query(
        "SELECT s.id, s.student_id, s.name, s.class_id FROM students ORDER BY s.name",
        default=[],
    )

    if request.method == "POST":
        class_id = request.form.get("class_id")
        att_date = request.form.get("att_date", date.today().isoformat())
        selected_ids = request.form.getlist("present_ids")

        if not class_id:
            flash("Please select a class.", "danger")
        else:
            # Fetch all students in this class
            class_students = _safe_query(
                "SELECT id FROM students WHERE class_id = %s", (class_id,), default=[]
            )
            now_time = datetime.now().time()
            for s in class_students:
                status = "present" if str(s["id"]) in selected_ids else "absent"
                _safe_query(
                    "INSERT INTO attendance (student_id, class_id, date, time, status, marked_by) "
                    "VALUES (%s, %s, %s, %s, %s, 'manual') "
                    "ON DUPLICATE KEY UPDATE status = VALUES(status), marked_by = 'manual'",
                    (s["id"], class_id, att_date, now_time, status),
                    fetch=False,
                )
            flash("Manual attendance saved.", "success")
            return redirect(url_for("attendance_records", class_id=class_id, date=att_date))

    return render_template("manual_attendance.html", classes=all_classes, students=students_list,
                           today=date.today())


# ---------------------------------------------------------------------------
# Routes – Reports & Emails
# ---------------------------------------------------------------------------

@app.route("/reports")
def reports():
    email_logs = _safe_query(
        "SELECT * FROM email_logs ORDER BY sent_at DESC LIMIT 50", default=[]
    )
    all_classes = _safe_query("SELECT id, name, subject, teacher_email FROM classes ORDER BY name", default=[])
    return render_template("reports.html", email_logs=email_logs, classes=all_classes,
                           today=date.today())


@app.route("/reports/send_daily", methods=["POST"])
def send_daily_report_route():
    class_id = request.form.get("class_id")
    report_date_str = request.form.get("report_date", date.today().isoformat())

    if not class_id:
        flash("Please select a class.", "danger")
        return redirect(url_for("reports"))

    try:
        report_date = date.fromisoformat(report_date_str)
    except ValueError:
        report_date = date.today()

    class_rows = _safe_query("SELECT * FROM classes WHERE id = %s", (class_id,), default=[])
    if not class_rows or not class_rows[0].get("teacher_email"):
        flash("Class not found or teacher email not set.", "danger")
        return redirect(url_for("reports"))

    cls = class_rows[0]

    # Fetch all students in class with their attendance
    report_rows = _safe_query(
        "SELECT s.student_id, s.name, "
        "COALESCE(a.status, 'absent') AS status "
        "FROM students s "
        "LEFT JOIN attendance a "
        "ON a.student_id = s.id AND a.class_id = %s AND a.date = %s "
        "WHERE s.class_id = %s "
        "ORDER BY s.name",
        (class_id, report_date, class_id),
        default=[],
    )

    sent = send_daily_report(cls["teacher_email"], f"{cls['name']} – {cls['subject']}", report_rows, report_date)
    if sent:
        flash(f"Report sent to {cls['teacher_email']}.", "success")
    else:
        flash("Failed to send email. Check SMTP configuration.", "danger")

    return redirect(url_for("reports"))


@app.route("/reports/low_attendance", methods=["POST"])
def send_low_attendance_route():
    """Send low-attendance alerts to all students below 75 % in a class."""
    class_id = request.form.get("class_id")
    if not class_id:
        flash("Please select a class.", "danger")
        return redirect(url_for("reports"))

    class_rows = _safe_query("SELECT * FROM classes WHERE id = %s", (class_id,), default=[])
    if not class_rows:
        flash("Class not found.", "danger")
        return redirect(url_for("reports"))
    cls = class_rows[0]

    # Total sessions held
    total_sessions = (_safe_query(
        "SELECT COUNT(DISTINCT date) AS c FROM attendance WHERE class_id = %s",
        (class_id,), default=[{"c": 0}]
    ) or [{"c": 0}])[0]["c"]

    if not total_sessions:
        flash("No attendance data found for this class.", "warning")
        return redirect(url_for("reports"))

    # Students with attendance < 75%
    low_students = _safe_query(
        "SELECT s.name, s.email, "
        "COUNT(a.id) AS present_count "
        "FROM students s "
        "LEFT JOIN attendance a ON a.student_id = s.id AND a.class_id = %s AND a.status = 'present' "
        "WHERE s.class_id = %s AND s.email IS NOT NULL "
        "GROUP BY s.id "
        "HAVING (COUNT(a.id) / %s) * 100 < 75",
        (class_id, class_id, total_sessions),
        default=[],
    )

    sent_count = 0
    for row in low_students:
        pct = (row["present_count"] / total_sessions) * 100
        ok = send_low_attendance_alert(
            row["email"], row["name"],
            f"{cls['name']} – {cls['subject']}", pct
        )
        if ok:
            sent_count += 1

    flash(f"Low-attendance alerts sent to {sent_count} student(s).", "success")
    return redirect(url_for("reports"))


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=app.config.get("FLASK_DEBUG", False), host="0.0.0.0", port=5000)
