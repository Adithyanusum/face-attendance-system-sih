-- Automated Attendance System – MySQL Schema
-- Run once to initialise the database.

CREATE DATABASE IF NOT EXISTS attendance_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE attendance_db;

-- -------------------------------------------------------
-- Classes / subjects
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS classes (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(100)  NOT NULL,
    subject      VARCHAR(100)  NOT NULL,
    teacher_name VARCHAR(150),
    teacher_email VARCHAR(200),
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- -------------------------------------------------------
-- Students (1 000 + records supported)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    student_id    VARCHAR(50)  NOT NULL UNIQUE,
    name          VARCHAR(150) NOT NULL,
    email         VARCHAR(200),
    class_id      INT,
    face_encoding LONGBLOB,          -- pickled numpy array of 128-d face encoding
    photo_path    VARCHAR(300),
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL,
    INDEX idx_student_id (student_id)
);

-- -------------------------------------------------------
-- Attendance log
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS attendance (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT  NOT NULL,
    class_id   INT  NOT NULL,
    date       DATE NOT NULL,
    time       TIME NOT NULL,
    status     ENUM('present', 'absent', 'late') DEFAULT 'present',
    marked_by  ENUM('face', 'manual') DEFAULT 'face',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (class_id)   REFERENCES classes(id)  ON DELETE CASCADE,
    UNIQUE KEY uq_attendance (student_id, class_id, date),
    INDEX idx_date (date),
    INDEX idx_class_date (class_id, date)
);

-- -------------------------------------------------------
-- Email notification log
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_logs (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    recipient   VARCHAR(200) NOT NULL,
    subject     VARCHAR(300) NOT NULL,
    body        TEXT,
    status      ENUM('sent', 'failed') DEFAULT 'sent',
    error_msg   TEXT,
    sent_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);
