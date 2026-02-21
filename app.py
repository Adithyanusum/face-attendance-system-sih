

from flask import Flask, render_template, request, redirect, url_for, session, Response, jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import subprocess
import sys
import cv2
import face_recognition
import pickle
import os
import time
from datetime import datetime
import csv
import numpy as np
import base64
import io
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
app.secret_key = "your_secret_key"  # required for login session

# Optional imports: allow the Flask app to start even if OpenCV or
# face_recognition (dlib) are not installed on the system.
try:
    import cv2
except Exception:
    cv2 = None

try:
    import face_recognition
except Exception:
    face_recognition = None

# Helper to create a JPEG bytes response with an error message
def _make_text_jpeg(msg, width=640, height=480):
    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    draw.text((10, height // 2 - 10), msg, fill=(0, 0, 0), font=font)
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return buf.getvalue()

# Remove any duplicate import blocks below (search for 'from flask import' etc.)

# Diagnostic route for email testing

# Camera-based attendance (PC/Mobile) routes
@app.route("/take_attendance_camera")
def take_attendance_camera():
    return render_template("take_attendance_camera.html")

@app.route("/api/mark_attendance", methods=["POST"])
def api_mark_attendance():
    import pandas as pd
    data = request.get_json()
    # If heavy dependencies are missing, return clear error for API callers
    if face_recognition is None or cv2 is None:
        return jsonify({"success": False, "error": "Face recognition or OpenCV not installed on server. Install dlib and opencv-python to enable this feature."})
    image_data = data.get("image", "")
    if not image_data.startswith("data:image/jpeg;base64,"):
        return jsonify({"success": False, "error": "Invalid image data"})
    try:
        img_str = image_data.split(",", 1)[1]
        img_bytes = base64.b64decode(img_str)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        return jsonify({"success": False, "error": f"Image decode error: {e}"})
    # Load encodings
    try:
        with open("data/encodings.pkl", "rb") as f:
            known_encodings, known_rolls = pickle.load(f)
    except Exception as e:
        return jsonify({"success": False, "error": "No face encodings found. Please register students first."})
    # Recognize face
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    faces = face_recognition.face_locations(rgb_frame)
    encodings = face_recognition.face_encodings(rgb_frame, faces)
    if not encodings:
        return jsonify({"success": False, "error": "No face detected."})
    # Use first face only
    face_enc = encodings[0]
    matches = face_recognition.compare_faces(known_encodings, face_enc, tolerance=0.5)
    roll = "Unknown"
    if True in matches:
        first_match_index = matches.index(True)
        roll = str(known_rolls[first_match_index])
    # Load student info
    student_file = "data/students.csv"
    students = {}
    if os.path.exists(student_file):
        df = pd.read_csv(student_file, dtype=str)
        for _, row in df.iterrows():
            students[str(row['roll_number'])] = row
    display_name = students[roll]['full_name'] if roll in students else roll
    standard_val = students[roll]['standard'] if roll in students else ''
    # Mark attendance if not already marked
    ts = time.time()
    date = datetime.fromtimestamp(ts).strftime("%d-%m-%Y")
    file_path = f"Attendance/Attendance_{date}.csv"
    marked_rolls = set()
    if os.path.exists(file_path):
        try:
            df_check = pd.read_csv(file_path)
            if 'ROLL' in df_check.columns:
                marked_rolls = set(df_check['ROLL'].astype(str).tolist())
        except Exception:
            pass
    timestamp = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
    name_val = display_name
    if roll != "Unknown" and roll not in marked_rolls:
        write_header = not os.path.exists(file_path)
        with open(file_path, "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            if write_header:
                writer.writerow(['ROLL', 'NAME', 'STANDARD', 'TIME'])
            writer.writerow([roll, name_val, standard_val, timestamp])
        
        # Send arrival email to parent
        parent_email = students[roll].get('parent_email', '') if roll in students else ''
        if parent_email:
            email_error = None
            try:
                GMAIL_USER = 'nusumadithya13@gmail.com'
                GMAIL_PASS = 'wymnrmhgnvflvagg'
                msg = MIMEMultipart()
                msg['From'] = GMAIL_USER
                msg['To'] = parent_email
                msg['Subject'] = 'School Arrival Notification'
                message_body = f"Your ward '{name_val}' of standard '{standard_val}' is present at school at {timestamp}."
                msg.attach(MIMEText(message_body, 'plain'))
                server = smtplib.SMTP('smtp.gmail.com', 587, timeout=15)
                server.starttls()
                server.login(GMAIL_USER, GMAIL_PASS)
                server.sendmail(GMAIL_USER, parent_email, msg.as_string())
                server.quit()
            except Exception as e:
                import traceback
                email_error = f"General error sending arrival email for {name_val} ({parent_email}): {e}\n{traceback.format_exc()}"
            if email_error:
                print(email_error)
                try:
                    log_path = os.path.join(os.path.dirname(__file__), 'email_errors.log')
                    with open(log_path, 'a') as logf:
                        logf.write(f"[{datetime.now()}] {email_error}\n")
                except Exception as log_ex:
                    print(f"Failed to write to email_errors.log: {log_ex}")

    if roll == "Unknown":
        return jsonify({"success": False, "error": "Face not recognized."})
    return jsonify({"success": True, "roll": roll, "name": name_val, "time": timestamp})

# ...existing code for routes and logic...

# Diagnostic route for email testing
@app.route('/test_email')
def test_email():
    import traceback
    GMAIL_USER = 'nusumadithya13@gmail.com'
    GMAIL_PASS = 'wymnrmhgnvflvagg'
    test_recipient = GMAIL_USER  # Send to yourself for testing
    subject = 'Test Email from Attendance System'
    body = 'This is a test email sent from your Flask attendance system.'
    msg = MIMEMultipart()
    msg['To'] = test_recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    server = smtplib.SMTP('smtp.gmail.com', 587, timeout=15)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(GMAIL_USER, GMAIL_PASS)
    response = server.sendmail(GMAIL_USER, test_recipient, msg.as_string())
    server.quit()
    print(f"Test email sent to {test_recipient}. SMTP response: {response}")
    return f"Test email sent to {test_recipient}. Check your inbox and spam folder. SMTP response: {response}"

# ---------- LOGIN CONFIG ----------
USERNAME = "TEACHER"
PASSWORD = "123456"

@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    if username == USERNAME and password == PASSWORD:
        session["user"] = username
        return redirect(url_for("dashboard"))
    else:
        return render_template("login.html", error="Invalid credentials")

@app.route("/dashboard")

def dashboard():
    if "user" not in session:
        return redirect(url_for("home"))
    return render_template("dashboard.html", user=session["user"])

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

@app.route("/add_details", methods=["GET", "POST"])
def add_details():
    import csv
    import datetime
    student_file = "data/students.csv"
    if request.method == "POST":
        full_name = request.form.get("full_name")
        dob = request.form.get("dob")
        parent_mobile = request.form.get("parent_mobile")
        parent_email = request.form.get("parent_email")
        standard = request.form.get("standard")
        year_joined = datetime.datetime.now().year
        # Generate roll number: YYYY-000X (FCFS)
        roll_number = None
        os.makedirs("data", exist_ok=True)
        students = []
        if os.path.exists(student_file):
            with open(student_file, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    students.append(row)
        count_this_year = sum(1 for s in students if s.get("year_joined") == str(year_joined))
        roll_number = f"{year_joined}{count_this_year+1:04d}"
        # Save student details
        with open(student_file, "a", newline="") as f:
            writer = csv.writer(f)
            if f.tell() == 0:
                writer.writerow(["roll_number", "full_name", "dob", "parent_mobile", "parent_email", "standard", "year_joined"])
            writer.writerow([roll_number, full_name, dob, parent_mobile, parent_email, standard, year_joined])
        # Store for face capture
        session["add_details_name"] = full_name
        session["add_details_roll"] = roll_number
        session["add_details_standard"] = standard
        return redirect(url_for("start_add_details"))
    return render_template("add_details.html")

def gen_frames():
    # If OpenCV is not available, stream a single error frame so the
    # video endpoint still responds instead of crashing the server.
    if cv2 is None:
        frame = _make_text_jpeg("OpenCV not available on server.")
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        return
    video = cv2.VideoCapture(0)
    while True:
        success, frame = video.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    video.release()

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/start_add_details", methods=["GET", "POST"])
def start_add_details():
    name = session.get("add_details_name")
    roll_number = session.get("add_details_roll")
    standard = session.get("add_details_standard")
    if not name or not roll_number or not standard:
        return redirect(url_for("add_details"))
    captured = False
    message = None
    if request.method == "POST":
        # Check availability of camera and face libs before capturing
        if cv2 is None or face_recognition is None:
            message = "Camera or face recognition library not available on server. Can't capture faces here."
        else:
            # Capture a frame from the webcam
            video = cv2.VideoCapture(0)
            ret, frame = video.read()
            video.release()
            if not ret:
                message = "Could not access camera."
            else:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                faces = face_recognition.face_locations(rgb_frame)
                encodings = []
                for (top, right, bottom, left) in faces:
                    face_enc = face_recognition.face_encodings(rgb_frame, [(top, right, bottom, left)])
                    if face_enc:
                        encodings.append(face_enc[0])
                if encodings:
                    os.makedirs("data", exist_ok=True)
                    if os.path.exists("data/encodings.pkl"):
                        with open("data/encodings.pkl", "rb") as f:
                            known_encodings, known_names = pickle.load(f)
                    else:
                        known_encodings, known_names = [], []
                    # Save roll_number as the face label
                    known_encodings.extend(encodings)
                    known_names.extend([roll_number] * len(encodings))
                    with open("data/encodings.pkl", "wb") as f:
                        pickle.dump((known_encodings, known_names), f)
                    captured = True
                    message = f"✅ Saved {len(encodings)} face(s) for {name} (Roll: {roll_number})."
                else:
                    message = "No face detected. Please try again."
    return render_template("camera_started.html", name=name, roll_number=roll_number, standard=standard, captured=captured, message=message)


# Take Attendance: Show name entry form, then POST to /start_attendance


# Real-time continuous attendance system
attendance_log = set()
def gen_attendance_frames():
    import pandas as pd
    import logging
    try:
        with open("data/encodings.pkl", "rb") as f:
            known_encodings, known_rolls = pickle.load(f)
    except Exception as e:
        logging.error(f"Error loading encodings: {e}")
        known_encodings, known_rolls = [], []
    import time
    time.sleep(1)  # Short delay to allow camera sensor to reset
    # If OpenCV or face_recognition are missing, stream an explanatory image
    if cv2 is None or face_recognition is None:
        frame = _make_text_jpeg("OpenCV or face_recognition not installed on server.")
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        return
    video = cv2.VideoCapture(0)
    # Reduce frame size for speed
    video.set(cv2.CAP_PROP_FRAME_WIDTH, 480)
    video.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
    if not video.isOpened():
        import numpy as np
        error_frame = np.ones((300, 600, 3), dtype=np.uint8) * 255
        cv2.putText(error_frame, "Camera not accessible!", (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,255), 3)
        ret, buffer = cv2.imencode('.jpg', error_frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        video.release()
        return
    ts = time.time()
    date = datetime.fromtimestamp(ts).strftime("%d-%m-%Y")
    file_path = f"Attendance/Attendance_{date}.csv"
    already_marked = set()
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        if 'ROLL' in df.columns:
            already_marked = set(df['ROLL'].tolist())
        elif 'NAME' in df.columns:
            already_marked = set(df['NAME'].tolist())
    # Load student info for display
    student_file = "data/students.csv"
    students = {}
    if os.path.exists(student_file):
        with open(student_file, "r") as f:
            reader = pd.read_csv(f)
            for _, row in reader.iterrows():
                students[str(row['roll_number'])] = row
    try:
        while True:
            success, frame = video.read()
            if not success:
                logging.error("Failed to read frame from camera.")
                break
            # Resize frame for faster processing
            frame = cv2.resize(frame, (480, 360))
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = face_recognition.face_locations(rgb_frame)
            encodings = face_recognition.face_encodings(rgb_frame, faces)
            for (top, right, bottom, left), face_enc in zip(faces, encodings):
                matches = face_recognition.compare_faces(known_encodings, face_enc, tolerance=0.5)
                roll = "Unknown"
                display_name = "Unknown"
                if True in matches:
                    first_match_index = matches.index(True)
                    roll = str(known_rolls[first_match_index])
                    display_name = students[roll]['full_name'] if roll in students else roll
                cv2.rectangle(frame, (left, top), (right, bottom), (50, 50, 255), 2)
                cv2.putText(frame, display_name, (left, top - 10), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 2)
                # Mark attendance only once per student per day
                if roll != "Unknown":
                    marked_rolls = set()
                    if os.path.exists(file_path):
                        try:
                            df_check = pd.read_csv(file_path)
                            if 'ROLL' in df_check.columns:
                                marked_rolls = set(df_check['ROLL'].astype(str).tolist())
                        except Exception:
                            pass
                    timestamp = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                    standard_val = students[roll]['standard'] if roll in students else ''
                    name_val = students[roll]['full_name'] if roll in students else roll
                    if roll not in marked_rolls:
                        write_header = not os.path.exists(file_path)
                        with open(file_path, "a", newline="") as csvfile:
                            writer = csv.writer(csvfile)
                            if write_header:
                                writer.writerow(['ROLL', 'NAME', 'STANDARD', 'TIME'])
                            writer.writerow([roll, name_val, standard_val, timestamp])
                        already_marked.add(roll)
                    # Send arrival email to parent immediately after attendance is marked
                    parent_email = students[roll].get('parent_email', '') if roll in students else ''
                    if parent_email:
                        email_error = None
                        try:
                            GMAIL_USER = 'nusumadithya13@gmail.com'
                            GMAIL_PASS = 'wymnrmhgnvflvagg'
                            msg = MIMEMultipart()
                            msg['From'] = GMAIL_USER
                            msg['To'] = parent_email
                            msg['Subject'] = 'School Arrival Notification'
                            message_body = f"Your ward '{display_name}' of standard '{standard_val}' is present at school at {timestamp}."
                            msg.attach(MIMEText(message_body, 'plain'))
                            print(f"Connecting to Gmail SMTP server...")
                            server = smtplib.SMTP('smtp.gmail.com', 587, timeout=15)
                            server.set_debuglevel(1)
                            server.ehlo()
                            server.starttls()
                            server.ehlo()
                            print(f"Logging in as {GMAIL_USER}")
                            server.login(GMAIL_USER, GMAIL_PASS)
                            print(f"Sending email to {parent_email}")
                            response = server.sendmail(GMAIL_USER, parent_email, msg.as_string())
                            print(f"SMTP sendmail response: {response}")
                            server.quit()
                            print(f"Email sent to {parent_email} for {display_name} at {timestamp}")
                        except smtplib.SMTPAuthenticationError as e:
                            email_error = f"Gmail SMTP Authentication Error: {e}"
                        except smtplib.SMTPRecipientsRefused as e:
                            email_error = f"Gmail SMTP Recipients Refused: {e.recipients}"
                        except smtplib.SMTPDataError as e:
                            email_error = f"Gmail SMTP Data Error: {e.smtp_code} {e.smtp_error}"
                        except smtplib.SMTPException as e:
                            email_error = f"Gmail SMTP Error: {e}"
                        except Exception as e:
                            import traceback
                            email_error = f"General error sending arrival email for {display_name} ({parent_email}): {e}\n{traceback.format_exc()}"
                        if email_error:
                            print(email_error)
                            try:
                                log_path = os.path.join(os.path.dirname(__file__), 'email_errors.log')
                                with open(log_path, 'a') as logf:
                                    logf.write(f"[{datetime.now()}] {email_error}\n")
                                print(f"Error logged to {log_path}")
                            except Exception as log_ex:
                                print(f"Failed to write to email_errors.log: {log_ex}")
            # Encode frame for streaming (restore JPEG quality)
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            # Restore original frame delay
            time.sleep(0.08)  # ~12 FPS
    finally:
        video.release()

@app.route('/attendance_feed')
def attendance_feed():
    return Response(gen_attendance_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/take_attendance")
def take_attendance():
    return render_template("take_attendance_realtime.html")

import glob
import pandas as pd

import glob
import pandas as pd

@app.route("/see_attendance", methods=["GET"])
def see_attendance():
    import glob
    import pandas as pd
    files = sorted(glob.glob("Attendance/Attendance_*.csv"))
    all_attendance = []
    for f in files:
        date = f.split("Attendance_")[1].split(".csv")[0]
        try:
            df = pd.read_csv(f)
            for row in df.values.tolist():
                # Add date to each record
                if len(row) == 4:
                    all_attendance.append([date] + row)
        except Exception:
            continue
    return render_template("see_attendance_calendar.html", attendance=all_attendance)


# See Students main page
@app.route("/see_students")
def see_students():
    import pandas as pd
    student_file = "data/students.csv"
    students_by_standard = {str(i): [] for i in range(1, 11)}
    if os.path.exists(student_file):
        df = pd.read_csv(student_file)
        for _, row in df.iterrows():
            # Skip rows missing 'standard' (e.g., empty or header-only)
            if 'standard' in row and not pd.isna(row['standard']):
                students_by_standard[str(row['standard'])].append(row)
    return render_template("see_students.html", students_by_standard=students_by_standard)


# Dynamic route for each standard
def send_absent_sms(absent_students, selected_date):
    # Email sending for absentees using Gmail SMTP
    # Set your Gmail credentials here
    GMAIL_USER = 'nusumadithya13@gmail.com'
    GMAIL_PASS = 'wymnrmhgnvflvagg'
    results = []
    for s in absent_students:
        email = str(s.get('parent_email', ''))
        name = s['full_name']
        standard = s['standard']
        message_body = f"Your ward '{name}' of standard '{standard}' was absent to school today ({selected_date})."
        if email:
            try:
                msg = MIMEMultipart()
                msg['From'] = GMAIL_USER
                msg['To'] = email
                msg['Subject'] = 'School Absence Notification'
                msg.attach(MIMEText(message_body, 'plain'))
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(GMAIL_USER, GMAIL_PASS)
                server.sendmail(GMAIL_USER, email, msg.as_string())
                server.quit()
                results.append((email, True, None))
            except Exception as e:
                results.append((email, False, str(e)))
        else:
            results.append((email, False, 'No email provided'))
    return results

@app.route("/students/standard<int:std>", methods=["GET", "POST"])
def students_by_standard(std):
    import pandas as pd
    from flask import request
    student_file = "data/students.csv"
    attendance_file = None
    students = []
    present_rolls = set()
    absent_rolls = set()
    total_students = 0
    total_present = 0
    total_absent = 0
    # Get selected date from query param
    # Support GET for attendance view, POST for sending SMS
    if request.method == "POST" and request.form.get("send_sms"):
        selected_date = request.form.get('date')
        send_sms_triggered = True
    else:
        selected_date = request.args.get('date')
        send_sms_triggered = False
    from datetime import datetime
    import time
    today_str = datetime.now().strftime("%Y-%m-%d")
    if not selected_date:
        selected_date = datetime.fromtimestamp(time.time()).strftime("%d-%m-%Y")
    if os.path.exists(student_file):
        df = pd.read_csv(student_file, dtype=str)
        students = [row for _, row in df.iterrows() if str(row['standard']) == str(std)]
        total_students = len(students)
    attendance_file = f"Attendance/Attendance_{selected_date}.csv"
    attendance_times = {}  # roll_number -> time
    if os.path.exists(attendance_file):
        import csv
        with open(attendance_file, 'r') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) >= 4:
                    attendance_times[str(row[0])] = row[3]
    present_rolls = set(attendance_times.keys())
    absent_rolls = set([s['roll_number'] for s in students if s['roll_number'] not in present_rolls])
    total_present = len(present_rolls & set([s['roll_number'] for s in students]))
    total_absent = len(absent_rolls)
    # Send SMS only if triggered by button
    sms_sent = False
    absent_students = [s for s in students if s['roll_number'] in absent_rolls]
    sms_results = None
    if send_sms_triggered and absent_students:
        sms_results = send_absent_sms(absent_students, selected_date)
        sms_sent = True
    return render_template(
        "students_standard.html",
        standard=std,
        students=students,
        total_students=total_students,
        total_present=total_present,
        total_absent=total_absent,
        present_rolls=present_rolls,
        absent_rolls=absent_rolls,
        selected_date=selected_date,
        sms_sent=sms_sent,
        sms_results=sms_results,
        attendance_times=attendance_times,
        today_str=today_str
    )

def students_by_standard(std):
    import pandas as pd
    from flask import request
    student_file = "data/students.csv"
    attendance_file = None
    students = []
    present_rolls = set()
    absent_rolls = set()
    total_students = 0
    total_present = 0
    total_absent = 0
    # Get selected date from query param
    # Support GET for attendance view, POST for sending SMS
    if request.method == "POST" and request.form.get("send_sms"):
        selected_date = request.form.get('date')
        send_sms_triggered = True
    else:
        selected_date = request.args.get('date')
        send_sms_triggered = False
    if not selected_date:
        import time
        from datetime import datetime
        selected_date = datetime.fromtimestamp(time.time()).strftime("%d-%m-%Y")
    if os.path.exists(student_file):
        df = pd.read_csv(student_file)
        students = [row for _, row in df.iterrows() if str(row['standard']) == str(std)]
        total_students = len(students)
    attendance_file = f"Attendance/Attendance_{selected_date}.csv"
    if os.path.exists(attendance_file):
        try:
            adf = pd.read_csv(attendance_file)
        except Exception:
            import csv
            with open(attendance_file, 'r') as f:
                reader = csv.reader(f)
                rows = list(reader)
            present_rolls = set()
            for row in rows:
                if len(row) == 4:
                    present_rolls.add(row[0])
                elif len(row) == 2:
                    present_rolls.update([s['roll_number'] for s in students if s['full_name'] == row[0]])
        else:
            if 'ROLL' in adf.columns:
                present_rolls = set(adf['ROLL'].tolist())
            elif 'NAME' in adf.columns:
                present_rolls = set([s['roll_number'] for s in students if s['full_name'] in adf['NAME'].tolist()])
    absent_rolls = set([s['roll_number'] for s in students if s['roll_number'] not in present_rolls])
    total_present = len(present_rolls & set([s['roll_number'] for s in students]))
    total_absent = len(absent_rolls)
    # Send SMS only if triggered by button
    sms_sent = False
    absent_students = [s for s in students if s['roll_number'] in absent_rolls]
    if send_sms_triggered and absent_students:
        send_absent_sms(absent_students, selected_date)
        sms_sent = True
    return render_template("students_standard.html", standard=std, students=students, total_students=total_students, total_present=total_present, total_absent=total_absent, present_rolls=present_rolls, absent_rolls=absent_rolls, selected_date=selected_date, sms_sent=sms_sent)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
