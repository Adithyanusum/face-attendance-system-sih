"""SMTP email notification service."""
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date

from config import Config

logger = logging.getLogger(__name__)


def _log_email(recipient: str, subject: str, body: str, status: str, error: str = ""):
    """Persist an email send attempt to the email_logs table (best-effort)."""
    try:
        from db import execute_query
        execute_query(
            "INSERT INTO email_logs (recipient, subject, body, status, error_msg) "
            "VALUES (%s, %s, %s, %s, %s)",
            (recipient, subject, body, status, error),
            fetch=False,
        )
    except Exception:  # never let logging errors surface to caller
        logger.exception("Failed to log email to database.")


def send_email(recipient: str, subject: str, html_body: str) -> bool:
    """Send an HTML email via SMTP.  Returns True on success."""
    if not Config.SMTP_USER or not Config.SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured – email not sent.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{Config.SMTP_FROM_NAME} <{Config.SMTP_FROM}>"
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            server.sendmail(Config.SMTP_FROM, recipient, msg.as_string())
        _log_email(recipient, subject, html_body, "sent")
        logger.info("Email sent to %s – %s", recipient, subject)
        return True
    except Exception as exc:
        _log_email(recipient, subject, html_body, "failed", str(exc))
        logger.exception("Failed to send email to %s.", recipient)
        return False


# ---------------------------------------------------------------------------
# Pre-built report helpers
# ---------------------------------------------------------------------------

def send_daily_report(teacher_email: str, class_name: str, report_rows: list, report_date: date | None = None):
    """Send a daily attendance summary to the class teacher."""
    if report_date is None:
        report_date = date.today()

    present = sum(1 for r in report_rows if r.get("status") == "present")
    absent = len(report_rows) - present

    rows_html = "".join(
        f"<tr>"
        f"<td>{r.get('student_id', '')}</td>"
        f"<td>{r.get('name', '')}</td>"
        f"<td style='color:{'green' if r.get('status') == 'present' else 'red'}'>"
        f"{r.get('status', '').capitalize()}</td>"
        f"</tr>"
        for r in report_rows
    )

    html = f"""
    <html><body>
    <h2>Daily Attendance Report – {class_name}</h2>
    <p><strong>Date:</strong> {report_date.strftime('%d %b %Y')}</p>
    <p>
      <strong>Present:</strong> {present} &nbsp;|&nbsp;
      <strong>Absent:</strong> {absent} &nbsp;|&nbsp;
      <strong>Total:</strong> {len(report_rows)}
    </p>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
      <thead style="background:#343a40;color:white">
        <tr><th>Student ID</th><th>Name</th><th>Status</th></tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    <p style="color:#888;font-size:12px">Sent automatically by the Face Attendance System.</p>
    </body></html>
    """
    subject = f"Attendance Report – {class_name} – {report_date.strftime('%d %b %Y')}"
    return send_email(teacher_email, subject, html)


def send_low_attendance_alert(student_email: str, student_name: str, class_name: str, percentage: float):
    """Send a low-attendance warning email to a student.

    Parameters
    ----------
    student_email:
        Recipient's email address.
    student_name:
        Student's full name (used in the email body).
    class_name:
        Subject/class identifier shown in the email.
    percentage:
        Current attendance percentage (0–100). The alert is typically sent
        when this falls below 75 %.

    Returns
    -------
    True if the email was delivered, False otherwise.
    """
    html = f"""
    <html><body>
    <h2>Low Attendance Alert</h2>
    <p>Dear <strong>{student_name}</strong>,</p>
    <p>Your current attendance in <strong>{class_name}</strong> is
       <span style="color:red"><strong>{percentage:.1f}%</strong></span>,
       which is below the required 75&nbsp;%.</p>
    <p>Please contact your class teacher immediately.</p>
    <p style="color:#888;font-size:12px">Face Attendance System – automated notification.</p>
    </body></html>
    """
    subject = f"Low Attendance Alert – {class_name}"
    return send_email(student_email, subject, html)
