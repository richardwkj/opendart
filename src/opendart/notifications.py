"""Notification module for failure alerts.

Per spec section 5.2: On job failure or critical errors, send an email notification.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from opendart.config import get_config

logger = logging.getLogger(__name__)


class NotificationError(Exception):
    """Raised when notification delivery fails."""

    pass


def send_email_notification(
    subject: str,
    body: str,
    recipient: str | None = None,
) -> bool:
    """Send an email notification.

    Args:
        subject: Email subject
        body: Email body text
        recipient: Override recipient email (defaults to config)

    Returns:
        True if sent successfully, False otherwise
    """
    config = get_config()

    smtp_host = config.get("SMTP_HOST")
    smtp_port = int(config.get("SMTP_PORT", "587"))
    smtp_user = config.get("SMTP_USER")
    smtp_password = config.get("SMTP_PASSWORD")
    notification_email = recipient or config.get("NOTIFICATION_EMAIL")

    if not all([smtp_host, smtp_user, smtp_password, notification_email]):
        logger.warning(
            "Email notification skipped: SMTP configuration incomplete. "
            "Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, and NOTIFICATION_EMAIL in .env"
        )
        return False

    try:
        msg = EmailMessage()
        msg["Subject"] = f"[OpenDART] {subject}"
        msg["From"] = smtp_user
        msg["To"] = notification_email
        msg.set_content(body)

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info(f"Email notification sent: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
        return False


def notify_job_failure(
    job_name: str,
    error: Exception | str,
    context: dict[str, Any] | None = None,
) -> bool:
    """Send notification about a job failure.

    Args:
        job_name: Name of the failed job
        error: Error that caused the failure
        context: Additional context information

    Returns:
        True if notification sent successfully
    """
    subject = f"Job Failed: {job_name}"

    body_lines = [
        f"Job '{job_name}' has failed.",
        "",
        f"Error: {error}",
        "",
    ]

    if context:
        body_lines.append("Context:")
        for key, value in context.items():
            body_lines.append(f"  {key}: {value}")

    body = "\n".join(body_lines)

    return send_email_notification(subject, body)


def notify_rate_limit_hit(
    action_taken: str,
    context: dict[str, Any] | None = None,
) -> bool:
    """Send notification about rate limit being hit.

    Args:
        action_taken: What action was taken (paused, exited)
        context: Additional context

    Returns:
        True if notification sent successfully
    """
    subject = "Rate Limit Hit (Error 020)"

    body_lines = [
        "DART API rate limit was exceeded.",
        "",
        f"Action taken: {action_taken}",
        "",
    ]

    if context:
        body_lines.append("Context:")
        for key, value in context.items():
            body_lines.append(f"  {key}: {value}")

    body = "\n".join(body_lines)

    return send_email_notification(subject, body)


def notify_sync_complete(
    stats: dict[str, Any],
) -> bool:
    """Send notification about successful sync completion.

    Args:
        stats: Job statistics

    Returns:
        True if notification sent successfully
    """
    subject = "Monthly Sync Completed"

    body_lines = [
        "The monthly DART data sync has completed successfully.",
        "",
        "Statistics:",
    ]

    for key, value in stats.items():
        body_lines.append(f"  {key}: {value}")

    body = "\n".join(body_lines)

    return send_email_notification(subject, body)
