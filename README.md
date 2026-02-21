<<<<<<< HEAD
# face-attendance-system-sih
Automated Attendance System (Smart India Hackathon) | Developer | 2025  Tech Stack: Python, Flask, MySQL, Bootstrap, SMTP  • Automated attendance tracking for 1,000+ student records.  • Reduced manual attendance time from 2 minutes to 15 seconds per class.  • Integrated SMTP-based email notifications for automated reporting.  
=======
# Face Attendance

Quick steps to run the attendance app locally on Windows.

Prerequisites
- Python 3.8/3.9/3.10 installed
- (Recommended on Windows) conda for easier `dlib` installation

1) Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2) (Recommended Windows / conda) If using conda, install `dlib` first:

```powershell
conda create -n faceatt python=3.9 -y
conda activate faceatt
conda install -c conda-forge dlib -y
```

3) Install Python requirements

```powershell
pip install -r requirements.txt
```

4) Run the app

```powershell
python app.py
```

5) Open the site
- Visit http://127.0.0.1:5000/ in your browser

Notes
- `face_recognition` depends on `dlib`. On Windows installing `dlib` via `conda` is usually easiest.
- The app expects `data/haarcascade_frontalface_default.xml` and `data/students.csv` to exist (some sample files are included in the repo). It will create `data/encodings.pkl` and `Attendance/` files as needed.
- The app uses Gmail SMTP settings hard-coded in `app.py`; update credentials or disable email features if you prefer not to send emails during testing.
>>>>>>> d3117fb (initial commit)
