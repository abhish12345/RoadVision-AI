"""
Email Service — sends notifications on task completion.
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


def send_task_completion_email(
    to_email: str,
    task_name: str,
    task_id: str,
    camera_type: str,
    total_detections: int,
    total_frames: int,
    road_health_score: Optional[float],
    report_path: Optional[str] = None
):
    """Send email notification when a task processing completes."""
    if not to_email:
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"✅ Road Survey Complete: {task_name}"
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = to_email

        camera_label = "PAVE Camera (Pavement Defects)" if camera_type == "pave" else "ROW Camera (Road Assets)"
        score_text = f"{road_health_score:.1f}/100" if road_health_score else "N/A"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #1a1a2e; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0;">🛣️ Road Survey Processing Complete</h2>
            </div>
            <div style="background: #f8f9fa; padding: 20px; border-radius: 0 0 8px 8px; border: 1px solid #dee2e6;">
                <h3 style="color: #333;">Task: {task_name}</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #dee2e6; color: #666;">Camera Type</td>
                        <td style="padding: 8px; border-bottom: 1px solid #dee2e6; font-weight: bold;">{camera_label}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #dee2e6; color: #666;">Frames Processed</td>
                        <td style="padding: 8px; border-bottom: 1px solid #dee2e6; font-weight: bold;">{total_frames:,}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #dee2e6; color: #666;">Total Detections</td>
                        <td style="padding: 8px; border-bottom: 1px solid #dee2e6; font-weight: bold;">{total_detections:,}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; color: #666;">Road Health Score</td>
                        <td style="padding: 8px; font-weight: bold; color: {'#28a745' if road_health_score and road_health_score >= 70 else '#ffc107' if road_health_score and road_health_score >= 40 else '#dc3545'};">
                            {score_text}
                        </td>
                    </tr>
                </table>
                <div style="margin-top: 20px; padding: 15px; background: #e8f4fd; border-radius: 6px;">
                    <p style="margin: 0; color: #0066cc;">
                        📊 View full results and download reports in your dashboard.
                    </p>
                </div>
                <p style="color: #999; font-size: 12px; margin-top: 20px;">
                    Task ID: {task_id}<br>
                    This is an automated notification from Road Identification System.
                </p>
            </div>
        </body>
        </html>
        """

        text = f"""
Road Survey Processing Complete

Task: {task_name}
Camera: {camera_label}
Frames Processed: {total_frames}
Total Detections: {total_detections}
Road Health Score: {score_text}

View results in your dashboard.
Task ID: {task_id}
        """

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        # Attach report if provided
        if report_path and Path(report_path).exists():
            with open(report_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={Path(report_path).name}"
                )
                msg.attach(part)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())

        logger.info(f"Email sent to {to_email} for task {task_id}")

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")


def send_processing_failed_email(to_email: str, task_name: str, task_id: str, error: str):
    """Send email when task processing fails."""
    if not to_email:
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"❌ Road Survey Failed: {task_name}"
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = to_email

        html = f"""
        <html><body style="font-family: Arial, sans-serif;">
            <div style="background: #dc3545; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h2>❌ Processing Failed</h2>
            </div>
            <div style="padding: 20px; border: 1px solid #dee2e6; border-radius: 0 0 8px 8px;">
                <p>Task <strong>{task_name}</strong> failed during processing.</p>
                <p style="color: #dc3545;">Error: {error}</p>
                <p style="color: #999; font-size: 12px;">Task ID: {task_id}</p>
            </div>
        </body></html>
        """
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())
    except Exception as e:
        logger.error(f"Failed to send failure email: {e}")
