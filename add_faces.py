

import cv2
import face_recognition
import pickle
import os
import sys
video = cv2.VideoCapture(0)
if len(sys.argv) > 1:
    name = sys.argv[1]
else:
    name = input("Enter Your Name: ")

encodings = []

while True:
    ret, frame = video.read()
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    faces = face_recognition.face_locations(rgb_frame)

    for (top, right, bottom, left) in faces:
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
        face_enc = face_recognition.face_encodings(rgb_frame, [(top, right, bottom, left)])
        if face_enc:
            encodings.append(face_enc[0])
            cv2.putText(frame, f"Samples: {len(encodings)}", (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    cv2.imshow("Capturing Faces", frame)

    if cv2.waitKey(1) & 0xFF == ord('q') or len(encodings) >= 20:  # capture 20 encodings
        break

video.release()
cv2.destroyAllWindows()

# Save encodings
os.makedirs("data", exist_ok=True)
if os.path.exists("data/encodings.pkl"):
    with open("data/encodings.pkl", "rb") as f:
        known_encodings, known_names = pickle.load(f)
else:
    known_encodings, known_names = [], []

known_encodings.extend(encodings)
known_names.extend([name] * len(encodings))

with open("data/encodings.pkl", "wb") as f:
    pickle.dump((known_encodings, known_names), f)

print(f"✅ Saved {len(encodings)} encodings for {name}")
