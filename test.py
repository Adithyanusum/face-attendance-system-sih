import cv2
import face_recognition
import pickle
import os
import csv
import time
from datetime import datetime
from win32com.client import Dispatch

def speak(str1):
    spk = Dispatch("SAPI.SpVoice")
    spk.Speak(str1)

# Load encodings
with open("data/encodings.pkl", "rb") as f:
    known_encodings, known_names = pickle.load(f)

video = cv2.VideoCapture(0)
imgBackground = cv2.imread("C:/Users/nusum/Downloads/face-attendence/background.png")
COL_NAMES = ['NAME', 'TIME']

# Keep track of who has already been marked
attendance_log = set()

# Ensure Attendance folder exists
os.makedirs("Attendance", exist_ok=True)

while True:
    ret, frame = video.read()
    if not ret:
        continue

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    faces = face_recognition.face_locations(rgb_frame)
    encodings = face_recognition.face_encodings(rgb_frame, faces)

    for (top, right, bottom, left), face_enc in zip(faces, encodings):
        matches = face_recognition.compare_faces(known_encodings, face_enc, tolerance=0.5)
        name = "Unknown"

        if True in matches:
            first_match_index = matches.index(True)
            name = known_names[first_match_index]

        # Draw rectangle and name
        cv2.rectangle(frame, (left, top), (right, bottom), (50, 50, 255), 2)
        cv2.putText(frame, name, (left, top - 10),
                    cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 2)

        # Automatically log attendance
        if name != "Unknown" and name not in attendance_log:
            ts = time.time()
            date = datetime.fromtimestamp(ts).strftime("%d-%m-%Y")
            timestamp = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            attendance = [name, timestamp]

            file_path = f"Attendance/Attendance_{date}.csv"
            write_header = not os.path.exists(file_path)

            with open(file_path, "a", newline="") as csvfile:
                writer = csv.writer(csvfile)
                if write_header:
                    writer.writerow(COL_NAMES)
                writer.writerow(attendance)

            attendance_log.add(name)
            speak(f"Attendance Taken for {name}")
            print(f"[INFO] Attendance logged for {name} at {timestamp}")

    # Display frame
    if imgBackground is not None:
        imgBackground[162:162 + 480, 55:55 + 640] = frame
        cv2.imshow("Frame", imgBackground)
    else:
        cv2.imshow("Frame", frame)

    # Quit key
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video.release()
cv2.destroyAllWindows()
